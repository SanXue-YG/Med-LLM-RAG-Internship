"""CLI 评测入口：端到端 pipeline 批量运行并导出 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGE06 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE06 / "src"))

from config import (  # noqa: E402
    DEFAULT_FUSION_STRATEGY,
    EMBED_MODEL,
    RERANK_MODEL,
    resolve_chroma,
    resolve_chunks_path,
    resolve_slim_path,
)
from pipeline import DEFAULT_DEMO_QUERIES, RetrievalPipeline, build_eval_report  # noqa: E402


def _load_queries(args: argparse.Namespace) -> list[str]:
    if args.queries_file:
        path = Path(args.queries_file)
        if not path.is_file():
            raise FileNotFoundError(f"queries file not found: {path}")
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln and not ln.startswith("#")]
    if args.queries:
        return list(args.queries)
    return list(DEFAULT_DEMO_QUERIES)


def main() -> None:
    parser = argparse.ArgumentParser(description="06 检索流水线评测")
    parser.add_argument(
        "--mode",
        choices=("sample", "full"),
        default="sample",
        help="sample=验证样本；full=全量库",
    )
    parser.add_argument(
        "--queries",
        nargs="*",
        help="待评测 query（默认 schedule 首批 5 条）",
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        help="每行一条 query 的文本文件",
    )
    parser.add_argument(
        "--fusion-strategy",
        default=DEFAULT_FUSION_STRATEGY,
        choices=("simple", "rrf", "weighted"),
        help="融合策略（默认 rrf）",
    )
    parser.add_argument("--top-k-vector", type=int, default=20)
    parser.add_argument("--top-k-keyword", type=int, default=20)
    parser.add_argument("--top-k-fused", type=int, default=30, help="融合候选池大小（供重排）")
    parser.add_argument("--top-k-final", type=int, default=10, help="最终返回条数")
    parser.add_argument(
        "--skip-rerank",
        action="store_true",
        help="跳过重排（仅测 enhance + 多路融合）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=STAGE06 / "outputs" / "samples" / "pipeline_eval.json",
        help="评测结果 JSON 路径",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅校验环境与路径，不运行 pipeline",
    )
    args = parser.parse_args()

    chunks = resolve_chunks_path(args.mode)
    chroma_dir, collection = resolve_chroma(args.mode)
    slim = resolve_slim_path()

    if args.check_only:
        info = {
            "mode": args.mode,
            "chunks_path": str(chunks),
            "chunks_exists": chunks.is_file(),
            "slim_path": str(slim),
            "slim_exists": slim.is_file(),
            "chroma_persist_dir": str(chroma_dir),
            "chroma_exists": chroma_dir.is_dir(),
            "collection": collection,
            "embed_model": EMBED_MODEL,
            "rerank_model": RERANK_MODEL,
            "fusion_default": DEFAULT_FUSION_STRATEGY,
            "status": "ready",
        }
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return

    queries = _load_queries(args)
    print(f"[eval] mode={args.mode} queries={len(queries)} fusion={args.fusion_strategy}")
    if args.skip_rerank:
        print("[eval] skip_rerank=True（不加载 reranker 模型）")

    pipeline = RetrievalPipeline.from_mode(
        args.mode,
        fusion_strategy=args.fusion_strategy,
        top_k_vector=args.top_k_vector,
        top_k_keyword=args.top_k_keyword,
        top_k_fused=args.top_k_fused,
        top_k_final=args.top_k_final,
        skip_rerank=args.skip_rerank,
        load_reranker=not args.skip_rerank,
    )

    results = pipeline.run_batch(queries)
    report = build_eval_report(
        results,
        mode=args.mode,
        fusion_strategy=args.fusion_strategy,
        top_k_final=args.top_k_final,
        skip_rerank=args.skip_rerank,
    )
    report["config"] = {
        "chunks_path": str(chunks),
        "chroma_dir": str(chroma_dir),
        "collection": collection,
        "embed_model": EMBED_MODEL,
        "rerank_model": RERANK_MODEL if not args.skip_rerank else None,
        "top_k_vector": args.top_k_vector,
        "top_k_keyword": args.top_k_keyword,
        "top_k_fused": args.top_k_fused,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[eval] 已导出: {args.output}")
    print(
        json.dumps(
            {
                "query_count": report["query_count"],
                "latency_p50_ms": report["summary"]["latency_ms"]["total_p50"],
                "latency_p95_ms": report["summary"]["latency_ms"]["total_p95"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
