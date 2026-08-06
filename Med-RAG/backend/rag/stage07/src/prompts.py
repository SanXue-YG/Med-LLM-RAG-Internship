"""医学提示工程模板：四阶段 PromptStage 定义与渲染。"""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any

PROMPT_PLACEHOLDERS = ("question", "context", "constraints", "output_format")


@dataclass
class PromptStage:
    """单个提示阶段配置。"""

    name: str
    system_prompt: str
    user_prompt_template: str
    temperature: float
    max_tokens: int

    def render_user_prompt(
        self,
        *,
        question: str,
        context: str,
        constraints: str = "",
        output_format: str = "",
    ) -> str:
        """按统一占位符渲染用户提示词。"""
        values = {
            "question": question,
            "context": context,
            "constraints": constraints,
            "output_format": output_format,
        }
        return self.user_prompt_template.format(**values)

    def to_payload(
        self,
        *,
        question: str,
        context: str,
        constraints: str = "",
        output_format: str = "",
    ) -> dict[str, Any]:
        """返回可直接喂给推理接口的阶段配置。"""
        return {
            "stage": self.name,
            "system_prompt": self.system_prompt,
            "user_prompt": self.render_user_prompt(
                question=question,
                context=context,
                constraints=constraints,
                output_format=output_format,
            ),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


def _template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            fields.add(field_name)
    return fields


def validate_prompt_stage(stage: PromptStage) -> list[str]:
    """检查模板是否使用统一占位符，返回缺失项。"""
    fields = _template_fields(stage.user_prompt_template)
    return [name for name in PROMPT_PLACEHOLDERS if name not in fields]


PROMPT_STAGES: dict[str, PromptStage] = {
    "evidence_evaluator": PromptStage(
        name="证据评估器",
        system_prompt=(
            "You are a medical evidence evaluator. "
            "Assess evidence quality and consistency conservatively."
        ),
        user_prompt_template=(
            "Question:\n{question}\n\n"
            "Retrieved Context:\n{context}\n\n"
            "Constraints:\n{constraints}\n\n"
            "Required Output Format:\n{output_format}\n\n"
            "Task:\n"
            "1) Extract key evidence statements and classify study type when possible.\n"
            "2) Mark each statement as strong/moderate/weak evidence with reason.\n"
            "3) Identify contradictions, missing data, and uncertainty.\n"
            "4) Do not provide final clinical advice in this stage."
        ),
        temperature=0.1,
        max_tokens=900,
    ),
    "answer_generator": PromptStage(
        name="答案生成器",
        system_prompt=(
            "You are a cautious medical assistant. "
            "Generate answers strictly grounded in provided evidence."
        ),
        user_prompt_template=(
            "Question:\n{question}\n\n"
            "Retrieved Context:\n{context}\n\n"
            "Constraints:\n{constraints}\n\n"
            "Required Output Format:\n{output_format}\n\n"
            "Task:\n"
            "1) Draft a direct answer based only on the context.\n"
            "2) Explicitly cite supporting evidence points (by chunk/source labels).\n"
            "3) State uncertainty where evidence is incomplete.\n"
            "4) Avoid unsupported claims and diagnosis-style certainty."
        ),
        temperature=0.2,
        max_tokens=1200,
    ),
    "critical_reviewer": PromptStage(
        name="批判性审查器",
        system_prompt=(
            "You are a strict critical reviewer for medical safety. "
            "Find overclaims, missing caveats, and potential risk."
        ),
        user_prompt_template=(
            "Question:\n{question}\n\n"
            "Retrieved Context:\n{context}\n\n"
            "Constraints:\n{constraints}\n\n"
            "Required Output Format:\n{output_format}\n\n"
            "Task:\n"
            "1) Challenge weakly supported statements and identify hallucination risk.\n"
            "2) Add necessary safety caveats, contraindication reminders, and scope limits.\n"
            "3) Propose concrete revisions for safer wording.\n"
            "4) Output review comments in a concise checklist."
        ),
        temperature=0.0,
        max_tokens=800,
    ),
    "final_assembler": PromptStage(
        name="最终组装器",
        system_prompt=(
            "You are a final response assembler for medical QA. "
            "Produce clear, structured, and risk-aware final output."
        ),
        user_prompt_template=(
            "Question:\n{question}\n\n"
            "Retrieved Context:\n{context}\n\n"
            "Constraints:\n{constraints}\n\n"
            "Required Output Format:\n{output_format}\n\n"
            "Task:\n"
            "1) Merge validated answer content and reviewer revisions.\n"
            "2) Keep claims bounded to available evidence.\n"
            "3) Include an evidence summary and explicit uncertainty statement.\n"
            "4) End with a short note recommending professional medical consultation when applicable."
        ),
        temperature=0.1,
        max_tokens=1000,
    ),
}


def render_prompt_stage(
    stage_key: str,
    *,
    question: str,
    context: str,
    constraints: str = "",
    output_format: str = "",
) -> dict[str, Any]:
    """按阶段 key 渲染单阶段 prompt 配置。"""
    if stage_key not in PROMPT_STAGES:
        available = ", ".join(sorted(PROMPT_STAGES.keys()))
        raise KeyError(f"Unknown stage '{stage_key}'. Available: {available}")

    stage = PROMPT_STAGES[stage_key]
    return stage.to_payload(
        question=question,
        context=context,
        constraints=constraints,
        output_format=output_format,
    )
