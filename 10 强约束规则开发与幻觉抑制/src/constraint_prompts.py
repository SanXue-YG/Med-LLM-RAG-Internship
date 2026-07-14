"""Strong-constraint system prompts for stage 10.

Layers (task book a–d):
  a) knowledge boundary — fixed refusal when evidence is insufficient
  b) citation rules — only use assigned [n] labels
  c) no fabrication — no data/conclusions beyond provided literature
  d) format rules — section headings, abbreviations, references

Inject via ``append_to()`` onto 08/07 stage system prompts (do not replace).
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .config import DEFAULT_CONFIG, Stage10Config
except ImportError:
    from config import DEFAULT_CONFIG, Stage10Config  # type: ignore[no-redef]

CONSTRAINT_HEADER = (
    "=== HARD CONSTRAINTS (MANDATORY — overrides conflicting instructions) ==="
)
CONSTRAINT_SEPARATOR = "\n\n---\n\n"


def _build_knowledge_boundary(refusal_en: str, refusal_zh: str) -> str:
    return (
        "KNOWLEDGE BOUNDARY:\n"
        "- Answer ONLY from the Retrieved Context / provided literature chunks.\n"
        "- Do NOT use external knowledge, training data, or assumptions.\n"
        "- If the question cannot be answered from the provided literature, you MUST "
        f"respond with exactly this sentence (English canonical):\n"
        f'  "{refusal_en}"\n'
        f"- Chinese equivalent (if responding in Chinese): {refusal_zh}\n"
        "- When refusing, output ONLY the refusal sentence (no extra advice, "
        "no speculative treatment suggestions)."
    )


def _build_citation_rules() -> str:
    return (
        "CITATION RULES:\n"
        "- Each context chunk is labeled with a temporary ID such as [1], [2], [3].\n"
        "- Use ONLY citation IDs that appear in the provided context (canonical [n]).\n"
        "- Do NOT cite [k] outside the assigned range (e.g. never cite [99] if only "
        "[1]–[5] were provided).\n"
        "- Place citation markers [n] next to key factual claims supported by that chunk.\n"
        "- Chinese alias [文献n] is acceptable but [n] is preferred."
    )


def _build_no_fabrication() -> str:
    return (
        "NO FABRICATION:\n"
        "- Do NOT add statistics, dosages, trial names, drug effects, or clinical "
        "conclusions that are not explicitly supported by the provided literature.\n"
        "- Do NOT infer or extrapolate beyond what the chunks state.\n"
        "- If evidence is partial, state uncertainty rather than filling gaps."
    )


def _build_format_rules() -> str:
    return (
        "OUTPUT FORMAT:\n"
        "- When answering (not refusing), include these sections using one of the "
        "accepted headings per section:\n"
        "  • Core Answer — headings: Core Answer | Answer | **Answer:** | 核心答案\n"
        "  • Evidence Summary — headings: Evidence Summary | Evidence | 证据总结\n"
        "  • References — headings: References | Sources | 参考文献\n"
        "- On first use of a medical abbreviation (e.g. MI, AF, T2DM), give the full "
        "form in parentheses: e.g. MI (myocardial infarction).\n"
        "- In References/Sources, list each cited source with at least title; "
        "journal and year when available.\n"
        "- When refusing (knowledge boundary), you may output only the fixed refusal "
        "sentence — section headings are not required."
    )


@dataclass(frozen=True)
class ConstraintPromptBundle:
    """Four-layer hard-constraint text bundle for system-prompt injection."""

    knowledge_boundary: str
    citation_rules: str
    no_fabrication: str
    format_rules: str
    refusal_en: str
    refusal_zh: str

    def as_system_prompt(self) -> str:
        """Concatenate all constraint layers into one system block."""
        parts = [
            CONSTRAINT_HEADER,
            self.knowledge_boundary,
            self.citation_rules,
            self.no_fabrication,
            self.format_rules,
        ]
        return "\n\n".join(p.strip() for p in parts if p.strip())

    def append_to(self, system_prompt: str) -> str:
        """Keep the original stage system prompt; append constraint block after it."""
        base = (system_prompt or "").strip()
        block = self.as_system_prompt()
        if not base:
            return block
        return f"{base}{CONSTRAINT_SEPARATOR}{block}"

    def layer_dict(self) -> dict[str, str]:
        """Named layers for notebook / debugging."""
        return {
            "knowledge_boundary": self.knowledge_boundary,
            "citation_rules": self.citation_rules,
            "no_fabrication": self.no_fabrication,
            "format_rules": self.format_rules,
        }


def default_constraint_bundle(
    config: Stage10Config | None = None,
) -> ConstraintPromptBundle:
    """Build the default bundle from ``Stage10Config`` refusal sentences."""
    cfg = config or DEFAULT_CONFIG
    return ConstraintPromptBundle(
        knowledge_boundary=_build_knowledge_boundary(cfg.refusal_en, cfg.refusal_zh),
        citation_rules=_build_citation_rules(),
        no_fabrication=_build_no_fabrication(),
        format_rules=_build_format_rules(),
        refusal_en=cfg.refusal_en,
        refusal_zh=cfg.refusal_zh,
    )
