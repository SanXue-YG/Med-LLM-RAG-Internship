"""07 生成模块与提示词工程第一部分 — 源码包。

本阶段范围（详见 ../schedule.md）：
- models.py            : DocumentChunk / AssembledContext 等数据结构（阶段 1）
- context_assembler.py : ContextAssembler 上下文组装器（阶段 2）
- prompts.py           : PromptStage + 四阶段医学提示模板（阶段 3）
- pipeline.py          : （可选）retrieve→assemble→prompt 轻量粘合层

上游输入契约见 ../输入候选格式约定.md（06 检索流水线 reranked / fused 候选 dict）。
"""
