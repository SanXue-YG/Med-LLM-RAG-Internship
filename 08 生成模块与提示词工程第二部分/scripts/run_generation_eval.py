"""阶段 5：批量生成评测脚本。

默认使用 06 离线样例 ``pipeline_eval.json`` 作为检索输入，批量跑固定 query，
输出：
- outputs/samples/generation_eval.json（最新快照）
- outputs/logs/generation_eval_YYYYmmdd_HHMMSS.json（历史日志）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_QUERIES = [
    "What is the treatment for MI?",
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "warfarin atrial fibrillation elderly",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage08 generation batch eval.")
    parser.add_argument(
        "--queries",
        nargs="*",
        default=DEFAULT_QUERIES,
        help="Queries to run. Defaults to schedule baseline queries.",
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        default=1200,
        help="Max context tokens for ContextAssembler.",
    )
    parser.add_argument(
        "--skip-evidence-eval",
        action="store_true",
        help="Skip evidence evaluator stage.",
    )
    parser.add_argument(
        "--skip-critical-review",
        action="store_true",
        help="Skip critical reviewer stage.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="LLM request timeout seconds.",
    )
    return parser.parse_args()


def _bootstrap_paths() -> dict[str, Path]:
    script_path = Path(__file__).resolve()
    stage08 = script_path.parents[1]
    root = stage08.parent
    stage07 = root / "07 生成模块与提示词工程第一部分"
    stage06 = root / "06 检索系统开发第二部分"

    sys.path.insert(0, str(stage08 / "src"))
    sys.path.insert(0, str(stage07 / "src"))

    return {
        "root": root,
        "stage06": stage06,
        "stage07": stage07,
        "stage08": stage08,
    }


class OfflineRetrievalAdapter:
    """用 06 离线 ``pipeline_eval.json`` 模拟 retrieval_pipeline.run。"""

    def __init__(self, payload_by_query: dict[str, dict[str, Any]], fallback: dict[str, Any]):
        self.payload_by_query = payload_by_query
        self.fallback = fallback

    def run(self, query: str) -> dict[str, Any]:
        payload = self.payload_by_query.get(query) or self.fallback
        return {
            "query": query,
            "retrieval": payload.get("retrieval", {"fused": []}),
            "reranked": payload.get("reranked", []),
        }


def main() -> None:
    args = _parse_args()
    paths = _bootstrap_paths()

    from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL
    from context_assembler import ContextAssembler
    from generation_pipeline import MedicalGenerationPipeline
    from llm_generator import LLMGenerator

    eval_file = paths["stage06"] / "outputs" / "samples" / "pipeline_eval.json"
    eval_payload = json.loads(eval_file.read_text(encoding="utf-8"))
    per_query: dict[str, dict[str, Any]] = {
        item["query"]: item for item in eval_payload.get("queries", [])
    }
    fallback = eval_payload.get("queries", [{}])[0]

    retrieval = OfflineRetrievalAdapter(per_query, fallback)
    assembler = ContextAssembler(tokenizer_name=None)
    llm = LLMGenerator(model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, timeout=args.timeout)
    pipe = MedicalGenerationPipeline(
        retrieval_pipeline=retrieval,
        context_assembler=assembler,
        llm_generator=llm,
        skip_evidence_eval=args.skip_evidence_eval,
        skip_critical_review=args.skip_critical_review,
        max_context_tokens=args.max_context_tokens,
    )

    results: list[dict[str, Any]] = []
    for query in args.queries:
        result = pipe.run(query)
        metrics = result["generation_metrics"]
        results.append(
            {
                "query": query,
                "answer": result["answer"],
                "sources": result["sources"],
                "generation_metrics": metrics,
                "intermediate_results": result["intermediate_results"],
            }
        )
        print(
            f"[OK] {query} | total={metrics['total_time_seconds']}s | "
            f"answer_len={len(result['answer'])} | sources={len(result['sources'])}"
        )

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "offline_sample_pipeline_eval",
        "query_count": len(results),
        "config": {
            "max_context_tokens": args.max_context_tokens,
            "skip_evidence_eval": args.skip_evidence_eval,
            "skip_critical_review": args.skip_critical_review,
            "model": OLLAMA_MODEL,
            "base_url": OLLAMA_BASE_URL,
        },
        "queries": results,
    }

    out_samples = paths["stage08"] / "outputs" / "samples" / "generation_eval.json"
    out_logs_dir = paths["stage08"] / "outputs" / "logs"
    out_logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_log = out_logs_dir / f"generation_eval_{stamp}.json"

    out_samples.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_log.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved sample: {out_samples}")
    print(f"Saved log:    {out_log}")


if __name__ == "__main__":
    main()
