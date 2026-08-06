"""Format validation: abbreviations, section headings, references.

Stage 3: runs after generation (and after CitationGuard). ``boundary_hit``
exempts the three-section requirement for fixed refusal answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

try:
    from .config import DEFAULT_CONFIG, Stage10Config
except ImportError:
    from config import DEFAULT_CONFIG, Stage10Config  # type: ignore[no-redef]

RefStrictness = Literal["relaxed", "strict"]

# Section aliases (schedule「格式别名」)
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "core_answer": (
        r"core\s+answer",
        r"\*\*answer:\*\*",
        r"^answer\s*:",
        r"^answer\b",
        r"核心答案",
    ),
    "evidence_summary": (
        r"evidence\s+summary",
        r"\*\*evidence\s+summary:\*\*",
        r"\*\*evidence:\*\*",
        r"^evidence\s*:",
        r"^evidence\b",
        r"证据总结",
    ),
    "references": (
        r"^references\b",
        r"^references\s*:",
        r"^sources\s*:",
        r"^sources\b",
        r"参考文献",
    ),
}

_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+\-]{0,9}\b")
_SOURCES_LINE_RE = re.compile(
    r"^\[(\d+)\]\s+(.+?)(?:\s*\(doc_id=|$)",
    re.MULTILINE,
)


@dataclass
class FormatCheckResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 1.0
    boundary_hit: bool = False
    sections_found: dict[str, bool] = field(default_factory=dict)
    abbrev_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": self.issues,
            "warnings": self.warnings,
            "score": self.score,
            "boundary_hit": self.boundary_hit,
            "sections_found": self.sections_found,
            "abbrev_issues": self.abbrev_issues,
        }


class FormatChecker:
    """Check medical answer format against stage-10 rules."""

    def __init__(
        self,
        abbrev_map: dict[str, str] | None = None,
        *,
        ref_strictness: RefStrictness = "relaxed",
        refusal_en: str | None = None,
        refusal_zh: str | None = None,
    ) -> None:
        self.abbrev_map = {k.upper(): v for k, v in (abbrev_map or {}).items()}
        self.ref_strictness = ref_strictness
        self.refusal_en = refusal_en or DEFAULT_CONFIG.refusal_en
        self.refusal_zh = refusal_zh or DEFAULT_CONFIG.refusal_zh

    def detect_boundary_hit(self, answer: str) -> bool:
        """True if answer contains the fixed refusal sentence."""
        text = (answer or "").strip().lower()
        if not text:
            return False
        if self.refusal_en.lower() in text:
            return True
        return self.refusal_zh in (answer or "")

    def check_abbrev_expansion(self, answer: str) -> list[str]:
        """Flag abbreviations whose first use lacks a full expansion nearby."""
        issues: list[str] = []
        if not answer or not self.abbrev_map:
            return issues

        seen: set[str] = set()
        for match in _WORD_RE.finditer(answer):
            token = match.group(0)
            key = token.upper()
            if key not in self.abbrev_map or key in seen:
                continue
            seen.add(key)
            expansion = self.abbrev_map[key]
            window = answer[max(0, match.start() - 40) : match.end() + 80]
            if _abbrev_expanded_in_window(token, expansion, window):
                continue
            issues.append(
                f"Abbreviation '{token}' first use should include full form "
                f"({expansion}), e.g. {token} ({expansion})."
            )
        return issues

    def check_required_sections(
        self,
        answer: str,
        *,
        boundary_hit: bool = False,
    ) -> tuple[dict[str, bool], list[str]]:
        """Return section presence map and missing-section issues."""
        if boundary_hit:
            return {k: True for k in _SECTION_ALIASES}, []

        found = {name: _section_present(answer, patterns) for name, patterns in _SECTION_ALIASES.items()}
        issues: list[str] = []
        labels = {
            "core_answer": "Core Answer / Answer",
            "evidence_summary": "Evidence Summary / Evidence",
            "references": "References / Sources",
        }
        for name, ok in found.items():
            if not ok:
                issues.append(f"Missing required section: {labels[name]}.")
        return found, issues

    def check_references_completeness(
        self,
        answer: str,
        sources: list[dict[str, Any]] | None = None,
        *,
        boundary_hit: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Return (issues, warnings) for reference metadata."""
        if boundary_hit:
            return [], []

        issues: list[str] = []
        warnings: list[str] = []

        if sources:
            for src in sources:
                title = (src.get("source_title") or "").strip()
                idx = src.get("index")
                if not title or title == "unknown_source":
                    issues.append(f"Source [{idx}] missing title.")
                journal = (src.get("journal") or src.get("journal_name") or "").strip()
                year = src.get("year") or src.get("pub_year")
                if not journal:
                    msg = f"Source [{idx}] missing journal."
                    if self.ref_strictness == "strict":
                        issues.append(msg)
                    else:
                        warnings.append(msg)
                if year is None or str(year).strip() == "":
                    msg = f"Source [{idx}] missing year."
                    if self.ref_strictness == "strict":
                        issues.append(msg)
                    else:
                        warnings.append(msg)
        else:
            # Parse Sources: block from answer text
            block_issues, block_warnings = _check_sources_block_in_answer(
                answer, strictness=self.ref_strictness
            )
            issues.extend(block_issues)
            warnings.extend(block_warnings)

        if not sources and not _has_sources_block(answer):
            issues.append("Missing References/Sources section or sources list.")

        return issues, warnings

    def check(
        self,
        answer: str,
        sources: list[dict[str, Any]] | None = None,
        *,
        boundary_hit: bool | None = None,
    ) -> FormatCheckResult:
        """Run all format checks and aggregate result."""
        boundary = (
            self.detect_boundary_hit(answer) if boundary_hit is None else boundary_hit
        )

        abbrev_issues = [] if boundary else self.check_abbrev_expansion(answer)
        sections_found, section_issues = self.check_required_sections(
            answer, boundary_hit=boundary
        )
        ref_issues, ref_warnings = self.check_references_completeness(
            answer, sources, boundary_hit=boundary
        )

        issues = section_issues + abbrev_issues + ref_issues
        warnings = ref_warnings
        ok = len(issues) == 0

        if ok and not warnings:
            score = 1.0
        elif ok and warnings:
            score = 0.85
        else:
            score = max(0.0, 1.0 - 0.25 * len(issues))

        return FormatCheckResult(
            ok=ok,
            issues=issues,
            warnings=warnings,
            score=round(score, 4),
            boundary_hit=boundary,
            sections_found=sections_found,
            abbrev_issues=abbrev_issues,
        )

    def soft_patch(self, answer: str, check: FormatCheckResult) -> tuple[str, bool]:
        """Light template patch: prepend missing section headings (conservative)."""
        if check.ok or check.boundary_hit:
            return answer, False

        patched = answer.strip()
        changed = False
        if not check.sections_found.get("core_answer"):
            patched = f"**Answer:**\n\n{patched}"
            changed = True
        if not check.sections_found.get("evidence_summary"):
            patched = f"{patched}\n\n**Evidence Summary:**\n- See cited sources."
            changed = True
        if not check.sections_found.get("references"):
            patched = f"{patched}\n\n**Sources:**\n(See evidence refs above.)"
            changed = True
        return patched, changed


def default_format_checker(
    abbrev_map: dict[str, str] | None = None,
    config: Stage10Config | None = None,
) -> FormatChecker:
    cfg = config or DEFAULT_CONFIG
    return FormatChecker(
        abbrev_map=abbrev_map,
        ref_strictness=cfg.ref_strictness,  # type: ignore[arg-type]
        refusal_en=cfg.refusal_en,
        refusal_zh=cfg.refusal_zh,
    )


def _section_present(answer: str, patterns: tuple[str, ...]) -> bool:
    text = answer or ""
    for line in text.splitlines():
        line_l = line.strip().lower()
        if not line_l:
            continue
        for pat in patterns:
            if re.search(pat, line_l, re.IGNORECASE):
                return True
    return False


def _abbrev_expanded_in_window(abbrev: str, expansion: str, window: str) -> bool:
    w_low = window.lower()
    exp_low = expansion.lower()
    abbr = abbrev.upper()
    # MI (myocardial infarction) or myocardial infarction (MI)
    if f"{abbr.lower()} ({exp_low})" in w_low:
        return True
    if f"{exp_low} ({abbr.lower()})" in w_low:
        return True
    if exp_low in w_low:
        return True
    return False


def _has_sources_block(answer: str) -> bool:
    return bool(re.search(r"^\s*sources\s*:", answer or "", re.IGNORECASE | re.MULTILINE))


def _check_sources_block_in_answer(
    answer: str,
    *,
    strictness: RefStrictness,
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    if not _has_sources_block(answer):
        return issues, warnings

    lines = [m for m in _SOURCES_LINE_RE.finditer(answer or "")]
    if not lines:
        warnings.append("Sources block present but no parseable [n] title lines.")
        return issues, warnings

    for m in lines:
        title = m.group(2).strip()
        if not title:
            issues.append(f"Source [{m.group(1)}] missing title in Sources block.")
        # journal/year rarely in 08 postprocess lines — warn in relaxed
        if "journal=" not in m.group(0).lower() and strictness == "relaxed":
            warnings.append(
                f"Source [{m.group(1)}] line has no journal/year (relaxed mode: warn only)."
            )
    return issues, warnings
