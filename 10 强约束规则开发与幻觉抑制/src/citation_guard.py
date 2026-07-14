"""Citation labeling, extraction, validation, and conservative repair.

Stage 2: assign [1]..[k] after 07 assemble; validate after 08 generate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

try:
    from .config import DEFAULT_CONFIG, Stage10Config
except ImportError:
    from config import DEFAULT_CONFIG, Stage10Config  # type: ignore[no-redef]

# Canonical [n] and Chinese 文献n / [文献n]
_CITATION_PATTERNS = (
    re.compile(r"\[(\d{1,4})\]"),
    re.compile(r"文献\s*(\d{1,4})"),
    re.compile(r"\[文献\s*(\d{1,4})\]"),
)

# Lines/blocks we skip when scanning for citations (metadata tails)
_SKIP_PREFIXES = ("sources:", "evidence refs:", "medical disclaimer:")


@dataclass
class LabeledContext:
    """Context after ``assign_labels`` — aligned with ``format_sources`` index."""

    context_text: str
    selected_chunks: list[Any]
    valid_ids: set[int]

    @property
    def max_id(self) -> int:
        return max(self.valid_ids) if self.valid_ids else 0


@dataclass
class CitationCheckResult:
    """Result of ``CitationGuard.validate``."""

    ok: bool
    extracted: list[int] = field(default_factory=list)
    valid_ids: set[int] = field(default_factory=set)
    invalid: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "extracted": self.extracted,
            "valid_ids": sorted(self.valid_ids),
            "invalid": self.invalid,
            "warnings": self.warnings,
            "issues": self.issues,
        }


class CitationGuard:
    """Assign chunk labels, extract citations, validate, retry hints, repair."""

    def __init__(
        self,
        *,
        missing_policy: Literal["warn", "fail"] = "warn",
        chunk_separator: str = "\n\n",
        label_template: str = "[{index}] ",
    ) -> None:
        self.missing_policy = missing_policy
        self.chunk_separator = chunk_separator
        self.label_template = label_template

    def assign_labels(
        self,
        chunks: list[Any],
        *,
        existing_context: str | None = None,
    ) -> LabeledContext:
        """Prefix each chunk with ``[1]``..``[k]`` and rebuild ``context_text``.

        Chunk order is preserved to match 08 ``format_sources`` (index from 1).
        If ``existing_context`` is provided it is ignored for rebuild — labels
        are always derived from ``chunks`` order.
        """
        del existing_context  # reserved for pipeline glue; rebuild from chunks
        parts: list[str] = []
        labeled_chunks: list[Any] = []
        valid_ids: set[int] = set()

        for index, chunk in enumerate(chunks, start=1):
            text = _chunk_text(chunk).strip()
            if not text:
                continue
            prefix = self.label_template.format(index=index)
            labeled_text = f"{prefix}{text}"
            parts.append(labeled_text)
            labeled_chunks.append(_tag_chunk_index(chunk, index))
            valid_ids.add(index)

        context_text = self.chunk_separator.join(parts)
        return LabeledContext(
            context_text=context_text,
            selected_chunks=labeled_chunks,
            valid_ids=valid_ids,
        )

    def extract_citations(self, answer: str) -> list[int]:
        """Extract citation IDs from answer body (deduped, ascending)."""
        if not answer:
            return []
        body = _answer_body_for_citation_scan(answer)
        found: set[int] = set()
        for pattern in _CITATION_PATTERNS:
            for match in pattern.finditer(body):
                found.add(int(match.group(1)))
        return sorted(found)

    def validate(
        self,
        answer: str,
        valid_ids: set[int],
        *,
        boundary_hit: bool = False,
    ) -> CitationCheckResult:
        """Validate citations against assigned chunk IDs."""
        extracted = self.extract_citations(answer)
        invalid = sorted(i for i in extracted if i not in valid_ids)
        issues: list[str] = []
        warnings: list[str] = []

        if invalid:
            issues.append(
                f"Invalid citation ID(s) outside valid range {sorted(valid_ids)}: {invalid}"
            )

        if not boundary_hit and valid_ids and not extracted:
            msg = "No citation markers [n] found in answer body."
            if self.missing_policy == "fail":
                issues.append(msg)
            else:
                warnings.append(msg)

        ok = len(issues) == 0
        return CitationCheckResult(
            ok=ok,
            extracted=extracted,
            valid_ids=set(valid_ids),
            invalid=invalid,
            warnings=warnings,
            issues=issues,
        )

    def build_retry_hint(self, check: CitationCheckResult) -> str:
        """User-side correction hint for a constrained re-generation."""
        lines = ["Citation validation failed. Revise the answer with these rules:"]
        if check.invalid:
            lines.append(
                f"- Remove or replace invalid citation IDs: {check.invalid}. "
                f"Only use {sorted(check.valid_ids)}."
            )
        for issue in check.issues:
            if issue not in lines:
                lines.append(f"- {issue}")
        for warn in check.warnings:
            lines.append(f"- Note: {warn}")
        lines.append("- Place [n] markers next to supported claims.")
        return "\n".join(lines)

    def retry_or_repair(
        self,
        answer: str,
        check: CitationCheckResult,
        *,
        prefer_repair: bool = True,
    ) -> tuple[str, bool]:
        """Conservative rule repair: strip invalid citation markers.

        Returns ``(text, repaired)``. Does not call LLM — retry is handled
        by the pipeline using ``build_retry_hint``.
        """
        if check.ok or not prefer_repair:
            return answer, False
        if not check.invalid:
            return answer, False

        repaired_text = answer
        for bad_id in check.invalid:
            repaired_text = re.sub(rf"\[{bad_id}\]", "", repaired_text)
            repaired_text = re.sub(rf"文献\s*{bad_id}\b", "", repaired_text)
            repaired_text = re.sub(rf"\[文献\s*{bad_id}\]", "", repaired_text)
        repaired_text = re.sub(r"[ \t]{2,}", " ", repaired_text)
        repaired_text = re.sub(r"\n{3,}", "\n\n", repaired_text).strip()
        return repaired_text, True


def default_citation_guard(config: Stage10Config | None = None) -> CitationGuard:
    cfg = config or DEFAULT_CONFIG
    policy = cfg.citation_missing_policy
    if policy not in ("warn", "fail"):
        policy = "warn"
    return CitationGuard(missing_policy=policy)  # type: ignore[arg-type]


def _chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("text") or "")
    return str(getattr(chunk, "text", "") or "")


def _tag_chunk_index(chunk: Any, index: int) -> Any:
    """Attach ``citation_index`` for downstream debugging (non-destructive)."""
    if isinstance(chunk, dict):
        out = dict(chunk)
        meta = dict(out.get("metadata") or {})
        meta["citation_index"] = index
        out["metadata"] = meta
        return out
    if hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
        chunk.metadata["citation_index"] = index
    return chunk


def _answer_body_for_citation_scan(answer: str) -> str:
    """Drop trailing Sources/Evidence refs/disclaimer blocks before scan."""
    lines: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip().lower()
        if any(stripped.startswith(p) for p in _SKIP_PREFIXES):
            break
        lines.append(line)
    return "\n".join(lines)
