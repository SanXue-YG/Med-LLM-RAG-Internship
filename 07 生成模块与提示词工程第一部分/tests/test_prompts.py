import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from prompts import (  # noqa: E402
    PROMPT_PLACEHOLDERS,
    PROMPT_STAGES,
    PromptStage,
    render_prompt_stage,
    validate_prompt_stage,
)


EXPECTED_STAGE_KEYS = {
    "evidence_evaluator",
    "answer_generator",
    "critical_reviewer",
    "final_assembler",
}


def test_prompt_stages_keys_complete():
    assert set(PROMPT_STAGES.keys()) == EXPECTED_STAGE_KEYS


def test_prompt_stage_fields_present():
    for key, stage in PROMPT_STAGES.items():
        assert isinstance(stage, PromptStage)
        assert stage.name
        assert stage.system_prompt
        assert stage.user_prompt_template
        assert 0.0 <= stage.temperature <= 1.0
        assert stage.max_tokens > 0


def test_all_placeholders_in_templates():
    for key, stage in PROMPT_STAGES.items():
        missing = validate_prompt_stage(stage)
        assert missing == [], f"{key} missing placeholders: {missing}"
    assert set(PROMPT_PLACEHOLDERS) == {"question", "context", "constraints", "output_format"}


def test_render_prompt_stage_fills_values():
    payload = render_prompt_stage(
        "answer_generator",
        question="What is metformin?",
        context="Evidence paragraph one.",
        constraints="Use only context.",
        output_format="JSON",
    )
    assert payload["stage"] == "答案生成器"
    assert "What is metformin?" in payload["user_prompt"]
    assert "Evidence paragraph one." in payload["user_prompt"]
    assert "Use only context." in payload["user_prompt"]
    assert "JSON" in payload["user_prompt"]
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 1200


def test_render_unknown_stage_raises():
    with pytest.raises(KeyError, match="Unknown stage"):
        render_prompt_stage("not_a_stage", question="q", context="c")
