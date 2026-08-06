"""医学实体正则（任务书 MEDICAL_PATTERNS 风格）。"""

from __future__ import annotations

import re

from models import EntityMatch

# 药物 / 疾病等：\b 单词边界，避免子串误匹配
MEDICAL_PATTERNS: dict[str, str] = {
    "drug": (
        r"\b(aspirin|metformin|atorvastatin|warfarin|insulin|"
        r"lisinopril|amlodipine|simvastatin|heparin|clopidogrel)\b"
    ),
    "disease": (
        r"\b(diabetes|hypertension|malaria|cardiovascular|"
        r"myocardial infarction|heart failure|stroke|"
        r"coronary artery disease|atrial fibrillation|cancer)\b"
    ),
}


def extract_entities(text: str, patterns: dict[str, str] | None = None) -> list[EntityMatch]:
    """识别医学实体，返回去重后的匹配列表（按出现位置）。"""
    patterns = patterns or MEDICAL_PATTERNS
    found: list[EntityMatch] = []
    seen: set[tuple[str, int]] = set()

    for entity_type, pattern in patterns.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            key = (m.group(0).lower(), m.start())
            if key in seen:
                continue
            seen.add(key)
            found.append(
                EntityMatch(
                    type=entity_type,
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                )
            )

    found.sort(key=lambda e: e.start)
    return found
