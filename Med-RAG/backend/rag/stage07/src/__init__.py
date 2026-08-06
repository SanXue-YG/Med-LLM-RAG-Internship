"""07 生成模块与提示词工程第一部分 — 源码包。

本阶段范围（详见 ../schedule.md）：
- models.py            : DocumentChunk / AssembledContext 等数据结构（阶段 1）
- context_assembler.py : ContextAssembler 上下文组装器（阶段 2）
- prompts.py           : PromptStage + 四阶段医学提示模板（阶段 3）
- pipeline.py          : （可选）retrieve→assemble→prompt 轻量粘合层

上游输入契约见 ../输入候选格式约定.md（06 检索流水线 reranked / fused 候选 dict）。
"""

try:
    from .context_assembler import (
        DEFAULT_DEDUP_THRESHOLD,
        DEFAULT_MAX_PER_SOURCE,
        DEFAULT_SOURCE_PENALTY,
        DEFAULT_TOKENIZER_NAME,
        ContextAssembler,
    )
    from .models import (
        AssembledContext,
        ContextMetadata,
        DocumentChunk,
        coerce_to_document_chunks,
        document_chunk_from_candidate,
    )
    from .prompts import (
        PROMPT_PLACEHOLDERS,
        PROMPT_STAGES,
        PromptStage,
        render_prompt_stage,
        validate_prompt_stage,
    )
except ImportError:
    from context_assembler import (  # type: ignore[no-redef]
        DEFAULT_DEDUP_THRESHOLD,
        DEFAULT_MAX_PER_SOURCE,
        DEFAULT_SOURCE_PENALTY,
        DEFAULT_TOKENIZER_NAME,
        ContextAssembler,
    )
    from models import (  # type: ignore[no-redef]
        AssembledContext,
        ContextMetadata,
        DocumentChunk,
        coerce_to_document_chunks,
        document_chunk_from_candidate,
    )
    from prompts import (  # type: ignore[no-redef]
        PROMPT_PLACEHOLDERS,
        PROMPT_STAGES,
        PromptStage,
        render_prompt_stage,
        validate_prompt_stage,
    )

__all__ = [
    "AssembledContext",
    "ContextAssembler",
    "ContextMetadata",
    "DEFAULT_DEDUP_THRESHOLD",
    "DEFAULT_MAX_PER_SOURCE",
    "DEFAULT_SOURCE_PENALTY",
    "DEFAULT_TOKENIZER_NAME",
    "DocumentChunk",
    "PROMPT_PLACEHOLDERS",
    "PROMPT_STAGES",
    "PromptStage",
    "coerce_to_document_chunks",
    "document_chunk_from_candidate",
    "render_prompt_stage",
    "validate_prompt_stage",
]
