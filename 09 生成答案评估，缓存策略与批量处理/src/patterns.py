"""Regex and keyword patterns for stage 09 evaluator."""

from __future__ import annotations

import re

PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")
DOSAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|ug|units?)\b", re.IGNORECASE)
TIME_RANGE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|years?)\b", re.IGNORECASE
)

SAFETY_KEYWORDS = (
    "risk",
    "side effect",
    "adverse",
    "adverse event",
    "contraindication",
    "bleeding",
    "toxicity",
)
TREATMENT_KEYWORDS = (
    "recommend",
    "recommended",
    "treatment",
    "therapy",
    "regimen",
    "management",
)
MECHANISM_KEYWORDS = (
    "mechanism",
    "pathway",
    "mode of action",
    "principle",
    "action",
)

# (signal_label, regex, weight)
HALLUCINATION_SIGNAL_PATTERNS = (
    ("studies_show_no_citation", re.compile(r"\b(?:studies show|research shows)\b", re.IGNORECASE), 0.2),
    ("has_been_proven", re.compile(r"\b(?:has been proven|proven to)\b", re.IGNORECASE), 0.2),
    ("absolute_100_percent", re.compile(r"\b100\s*%", re.IGNORECASE), 0.3),
    (
        "absolute_safety_efficacy",
        re.compile(r"\b(?:completely|totally|absolutely)\s+(?:safe|effective|harmless)\b", re.IGNORECASE),
        0.3,
    ),
)

