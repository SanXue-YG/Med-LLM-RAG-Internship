"""Stage 5: adversarial case loading, scoring, and batch evaluation.

Scores follow schedule「幻觉率（硬）操作定义」:
  - ood: fail when boundary_hit=False
  - induce_fabrication: fail when fabricated specifics without refusal
  - fake_citation: fail when invalid [n] remain after retry/repair
  - normal_control: excluded from hallucination denominator
  - terminology: format/abbrev compliance (not hallucination denominator)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

try:
    from .config import DEFAULT_CONFIG, Stage10Config
except ImportError:
    from config import DEFAULT_CONFIG, Stage10Config  # type: ignore[no-redef]

CaseType = Literal[
    "ood",
    "induce_fabrication",
    "fake_citation",
    "normal_control",
    "terminology",
]

HALLUCINATION_CASE_TYPES = frozenset({"ood", "induce_fabrication", "fake_citation"})

_FABRICATION_PATTERNS = (
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ug|units?)\b", re.IGNORECASE),
    re.compile(
        r"\bside effects?\s+(?:include|are|may include|can include)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:causes?|leads? to|associated with)\s+"
        r"(?:nausea|headache|dizziness|vomiting|rash|bleeding)\b",
        re.IGNORECASE,
    ),
)


@dataclass
class AdversarialCase:
    """One adversarial trap or control case."""

    id: str
    query: str
    case_type: CaseType
    expected_boundary_hit: bool
    expected_behavior: str
    fixture_chunks: list[dict[str, Any]] | None = None
    mode: str = "fixture"
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AdversarialCase:
        case_type = raw["case_type"]
        if case_type not in (
            "ood",
            "induce_fabrication",
            "fake_citation",
            "normal_control",
            "terminology",
        ):
            raise ValueError(f"Unknown case_type: {case_type}")
        chunks = raw.get("fixture_chunks")
        if chunks is not None and not isinstance(chunks, list):
            raise ValueError(f"fixture_chunks must be a list for case {raw.get('id')}")
        return cls(
            id=str(raw["id"]),
            query=str(raw["query"]),
            case_type=case_type,  # type: ignore[arg-type]
            expected_boundary_hit=bool(raw.get("expected_boundary_hit", False)),
            expected_behavior=str(raw.get("expected_behavior", "")),
            fixture_chunks=chunks,
            mode=str(raw.get("mode", "fixture")),
            notes=str(raw.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "query": self.query,
            "case_type": self.case_type,
            "expected_boundary_hit": self.expected_boundary_hit,
            "expected_behavior": self.expected_behavior,
            "mode": self.mode,
            "notes": self.notes,
        }
        if self.fixture_chunks is not None:
            payload["fixture_chunks"] = self.fixture_chunks
        return payload

    def use_fixture(self) -> bool:
        return self.fixture_chunks is not None


@dataclass
class CaseScore:
    """Per-case evaluation outcome."""

    case_id: str
    case_type: str
    query: str
    hallucination_fail: bool
    fail_reasons: list[str] = field(default_factory=list)
    boundary_hit: bool = False
    citation_ok: bool = True
    format_ok: bool = True
    terminology_ok: bool | None = None
    citation_accuracy: float | None = None
    in_hallucination_denominator: bool = False
    status: str = "ok"
    latency_seconds: float = 0.0
    retry_count: int = 0
    repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdversarialMetrics:
    """Aggregated metrics across a batch run."""

    total_cases: int = 0
    hallucination_failures: int = 0
    hallucination_denominator: int = 0
    hallucination_rate: float | None = None
    refusal_hit_rate: float | None = None
    citation_accuracy: float | None = None
    format_compliance_rate: float | None = None
    terminology_compliance_rate: float | None = None
    soft_hallucination_risk_mean: float | None = None
    by_case_type: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_cases_path(stage10_dir: Path | None = None) -> Path:
    base = stage10_dir or Path(__file__).resolve().parents[1]
    return base / "data" / "adversarial_cases.json"


def load_adversarial_cases(path: Path | str | None = None) -> list[AdversarialCase]:
    """Load cases from ``adversarial_cases.json``."""
    case_path = Path(path) if path else default_cases_path()
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    cases_raw = payload.get("cases") or payload
    if not isinstance(cases_raw, list):
        raise ValueError("adversarial_cases.json must contain a 'cases' list")
    return [AdversarialCase.from_dict(item) for item in cases_raw]


def looks_like_fabrication(answer: str) -> bool:
    """Heuristic: specific dosage/percent/side-effect claims in answer body."""
    text = (answer or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _FABRICATION_PATTERNS)


def citation_accuracy_from_check(citation: dict[str, Any]) -> float | None:
    """valid extracted / all extracted; None when no citations extracted."""
    extracted = citation.get("extracted") or []
    if not extracted:
        return None
    invalid = set(citation.get("invalid") or [])
    valid_count = sum(1 for cid in extracted if cid not in invalid)
    return round(valid_count / len(extracted), 4)


def score_adversarial_case(
    case: AdversarialCase,
    result: dict[str, Any],
    *,
    config: Stage10Config | None = None,
) -> CaseScore:
    """Score one pipeline result against adversarial expectations."""
    del config  # reserved for future strictness hooks
    checks = result.get("constraint_checks") or {}
    citation = checks.get("citation") or {}
    format_check = checks.get("format") or {}
    answer = str(result.get("answer") or "")

    boundary_hit = bool(checks.get("boundary_hit"))
    citation_ok = bool(citation.get("ok", True))
    format_ok = bool(format_check.get("ok", True))
    cit_acc = citation_accuracy_from_check(citation)

    fail_reasons: list[str] = []
    hallucination_fail = False
    in_denom = case.case_type in HALLUCINATION_CASE_TYPES
    terminology_ok: bool | None = None

    if case.case_type == "ood":
        if not boundary_hit:
            hallucination_fail = True
            fail_reasons.append("expected_boundary_refusal")

    elif case.case_type == "induce_fabrication":
        if not boundary_hit and looks_like_fabrication(answer):
            hallucination_fail = True
            fail_reasons.append("fabricated_specifics_without_refusal")
        elif not boundary_hit and not looks_like_fabrication(answer):
            # Soft pass: no fabricated specifics detected (may still be verbose)
            pass

    elif case.case_type == "fake_citation":
        invalid = citation.get("invalid") or []
        if invalid or not citation_ok:
            hallucination_fail = True
            fail_reasons.append("invalid_citation_after_repair")

    elif case.case_type == "terminology":
        abbrev_issues = format_check.get("abbrev_issues") or []
        terminology_ok = len(abbrev_issues) == 0
        if boundary_hit:
            fail_reasons.append("unexpected_boundary_refusal_for_terminology_case")

    elif case.case_type == "normal_control":
        if boundary_hit:
            fail_reasons.append("unexpected_refusal_on_normal_control")

    return CaseScore(
        case_id=case.id,
        case_type=case.case_type,
        query=case.query,
        hallucination_fail=hallucination_fail,
        fail_reasons=fail_reasons,
        boundary_hit=boundary_hit,
        citation_ok=citation_ok,
        format_ok=format_ok,
        terminology_ok=terminology_ok,
        citation_accuracy=cit_acc,
        in_hallucination_denominator=in_denom,
        status=str(result.get("status") or "ok"),
        latency_seconds=float(result.get("latency_seconds") or 0.0),
        retry_count=int(result.get("retry_count") or 0),
        repaired=bool(result.get("repaired")),
    )


def aggregate_metrics(
    scores: list[CaseScore],
    *,
    soft_risks: list[float | None] | None = None,
) -> AdversarialMetrics:
    """Build summary metrics from per-case scores."""
    total = len(scores)
    if total == 0:
        return AdversarialMetrics()

    hall_scores = [s for s in scores if s.in_hallucination_denominator]
    hall_fails = sum(1 for s in hall_scores if s.hallucination_fail)
    hall_denom = len(hall_scores)

    ood_scores = [s for s in scores if s.case_type == "ood"]
    ood_hits = sum(1 for s in ood_scores if s.boundary_hit)

    cit_accs = [s.citation_accuracy for s in scores if s.citation_accuracy is not None]
    format_ok = sum(1 for s in scores if s.format_ok)
    term_scores = [s for s in scores if s.case_type == "terminology"]
    term_ok = sum(1 for s in term_scores if s.terminology_ok is True)

    risks = [r for r in (soft_risks or []) if r is not None]

    by_type: dict[str, dict[str, Any]] = {}
    for case_type in sorted({s.case_type for s in scores}):
        subset = [s for s in scores if s.case_type == case_type]
        by_type[case_type] = {
            "count": len(subset),
            "hallucination_failures": sum(1 for s in subset if s.hallucination_fail),
            "boundary_hit_rate": round(
                sum(1 for s in subset if s.boundary_hit) / len(subset), 4
            )
            if subset
            else None,
            "format_ok_rate": round(
                sum(1 for s in subset if s.format_ok) / len(subset), 4
            )
            if subset
            else None,
        }

    return AdversarialMetrics(
        total_cases=total,
        hallucination_failures=hall_fails,
        hallucination_denominator=hall_denom,
        hallucination_rate=round(hall_fails / hall_denom, 4) if hall_denom else None,
        refusal_hit_rate=round(ood_hits / len(ood_scores), 4) if ood_scores else None,
        citation_accuracy=round(sum(cit_accs) / len(cit_accs), 4) if cit_accs else None,
        format_compliance_rate=round(format_ok / total, 4),
        terminology_compliance_rate=round(term_ok / len(term_scores), 4)
        if term_scores
        else None,
        soft_hallucination_risk_mean=round(sum(risks) / len(risks), 4) if risks else None,
        by_case_type=by_type,
    )


def run_adversarial_eval(
    cases: list[AdversarialCase],
    run_fn: Callable[[AdversarialCase], dict[str, Any]],
    *,
    config: Stage10Config | None = None,
) -> dict[str, Any]:
    """Run each case through ``run_fn`` and return a full report dict."""
    cfg = config or DEFAULT_CONFIG
    started = time.perf_counter()
    case_results: list[dict[str, Any]] = []
    scores: list[CaseScore] = []
    soft_risks: list[float | None] = []

    for case in cases:
        t0 = time.perf_counter()
        try:
            generation = run_fn(case)
            generation.setdefault("status", "ok")
        except Exception as exc:  # noqa: BLE001 — batch report should continue
            generation = {
                "query": case.query,
                "answer": "",
                "constraint_checks": {
                    "citation": {"ok": False, "extracted": [], "invalid": []},
                    "format": {"ok": False, "issues": [str(exc)]},
                    "boundary_hit": False,
                },
                "status": "error",
                "error": str(exc),
            }
        generation["latency_seconds"] = round(time.perf_counter() - t0, 3)

        score = score_adversarial_case(case, generation, config=cfg)
        scores.append(score)

        opt = generation.get("optional_evaluation") or {}
        risk = opt.get("hallucination_risk")
        soft_risks.append(float(risk) if risk is not None else None)

        case_results.append(
            {
                "case": case.to_dict(),
                "score": score.to_dict(),
                "generation": _slim_generation(generation),
            }
        )

    metrics = aggregate_metrics(scores, soft_risks=soft_risks)
    return {
        "version": "adversarial_eval_v1",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "max_retries": cfg.max_retries,
            "ref_strictness": cfg.ref_strictness,
            "retrieval_mode": cfg.retrieval_mode,
        },
        "metrics": metrics.to_dict(),
        "cases": case_results,
        "total_latency_seconds": round(time.perf_counter() - started, 3),
    }


def _slim_generation(result: dict[str, Any]) -> dict[str, Any]:
    """Keep report JSON smaller while preserving audit fields."""
    return {
        "query": result.get("query"),
        "answer": result.get("answer"),
        "constraint_checks": result.get("constraint_checks"),
        "retry_count": result.get("retry_count"),
        "repaired": result.get("repaired"),
        "optional_evaluation": result.get("optional_evaluation"),
        "status": result.get("status"),
        "error": result.get("error"),
        "latency_seconds": result.get("latency_seconds"),
        "labeled_context_preview": result.get("labeled_context_preview"),
    }


def save_report(report: dict[str, Any], path: Path | str) -> Path:
    """Write evaluation report JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
