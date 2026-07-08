"""Stage 7 helpers: full-corpus live evaluation (notebook + CLI)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

CORPUS_SIZE_HINT = 6_107_296

DEFAULT_STAGE09_QUERIES = [
    "What is the treatment for MI?",
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "warfarin atrial fibrillation elderly",
]


def load_ground_truth(stage09: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads((stage09 / "data" / "ground_truth.json").read_text(encoding="utf-8"))
    return {item["query"]: item for item in payload.get("queries", [])}


def _load_stage08_bootstrap(stage08: Path) -> Any:
    path = stage08 / "src" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("stage08_bootstrap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load stage08 bootstrap: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_stage06_config(stage06: Path) -> Any:
    path = stage06 / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("stage06_config", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load stage06 config: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_full_corpus_resources(stage06: Path) -> dict[str, Any]:
    """Mirror ``run_retrieval_eval.py --check-only --mode full`` for notebooks."""
    cfg = _load_stage06_config(stage06)

    chunks = cfg.resolve_chunks_path("full")
    chroma_dir, collection = cfg.resolve_chroma("full")
    slim = cfg.resolve_slim_path()
    ready = chunks.is_file() and slim.is_file() and chroma_dir.is_dir()
    return {
        "mode": "full",
        "chunks_path": str(chunks),
        "chunks_exists": chunks.is_file(),
        "slim_path": str(slim),
        "slim_exists": slim.is_file(),
        "chroma_persist_dir": str(chroma_dir),
        "chroma_exists": chroma_dir.is_dir(),
        "collection": collection,
        "corpus_size_hint": CORPUS_SIZE_HINT,
        "ready": ready,
        "status": "ready" if ready else "missing_resources",
    }


def probe_ollama(stage08: Path, *, timeout: float = 5.0) -> dict[str, Any]:
    import httpx

    boot = _load_stage08_bootstrap(stage08)
    base_url = str(boot.OLLAMA_BASE_URL)
    model = str(boot.OLLAMA_MODEL)
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        ok = response.status_code == 200
        models: list[str] = []
        if ok:
            models = [str(item.get("name", "")) for item in response.json().get("models", [])]
        model_available = model in models or any(model.split(":")[0] in m for m in models)
        return {
            "ok": ok,
            "base_url": base_url,
            "model_requested": model,
            "model_available": model_available,
            "models_preview": models[:8],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "base_url": base_url,
            "model_requested": model,
            "model_available": False,
            "error": str(exc),
        }


def top_reranked_doc_id(payload: dict[str, Any]) -> str | None:
    reranked = payload.get("reranked") or []
    if not reranked:
        return None
    first = reranked[0]
    if isinstance(first, dict):
        return str(first.get("doc_id") or first.get("chunk_id") or "")
    return str(getattr(first, "doc_id", "") or getattr(first, "chunk_id", "") or "")


def compare_pipeline_eval_snapshots(
    sample_path: Path,
    full_path: Path,
    *,
    queries: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compare Top-1 reranked doc_id between sample and full pipeline_eval JSON."""
    if not sample_path.is_file():
        raise FileNotFoundError(f"sample pipeline eval not found: {sample_path}")
    if not full_path.is_file():
        raise FileNotFoundError(f"full pipeline eval not found: {full_path}")

    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))
    full_payload = json.loads(full_path.read_text(encoding="utf-8"))
    sample_by_query = {item["query"]: item for item in sample_payload.get("queries", [])}
    full_by_query = {item["query"]: item for item in full_payload.get("queries", [])}

    target_queries = queries or sorted(set(sample_by_query) | set(full_by_query))
    rows: list[dict[str, Any]] = []
    for query in target_queries:
        sample_item = sample_by_query.get(query, {})
        full_item = full_by_query.get(query, {})
        sample_top = top_reranked_doc_id(sample_item)
        full_top = top_reranked_doc_id(full_item)
        rows.append(
            {
                "query": query,
                "sample_top_doc_id": sample_top,
                "full_top_doc_id": full_top,
                "top_doc_changed": sample_top != full_top,
                "sample_reranked_count": len(sample_item.get("reranked") or []),
                "full_reranked_count": len(full_item.get("reranked") or []),
            }
        )
    return rows


def _ensure_upstream_import_context(stage06: Path, stage07: Path, stage08: Path) -> Any:
    """Prepare imports for 06/07/08 when stage09 already registered ``bootstrap`` / ``config``."""
    for stage in (stage06, stage07, stage08):
        src_path = (stage / "src").resolve()
        if not src_path.is_dir():
            continue
        sp = str(src_path)
        if sp in sys.path:
            sys.path.remove(sp)
        sys.path.insert(0, sp)

    boot08 = _load_stage08_bootstrap(stage08)
    sys.modules["bootstrap"] = boot08
    sys.modules["config"] = _load_stage06_config(stage06)

    # Drop partially-imported upstream modules so they reload with corrected context.
    for name in (
        "llm_generator",
        "generation_pipeline",
        "context_assembler",
        "pipeline",
        "json_utils",
        "postprocess",
        "prompts",
        "models",
    ):
        sys.modules.pop(name, None)

    return boot08


def build_live_full_generation_pipeline(
    stage06: Path,
    stage07: Path,
    stage08: Path,
    *,
    skip_evidence_eval: bool = True,
    skip_critical_review: bool = True,
    max_context_tokens: int = 1200,
    timeout: float = 180.0,
    skip_rerank: bool = False,
    fusion_strategy: str = "rrf",
) -> tuple[Any, str]:
    """Wire 06 full retrieval + 07 assembler + 08 Ollama generation."""
    boot = _ensure_upstream_import_context(stage06, stage07, stage08)

    # 1) Import 07/08 modules first (these need stage07 ``models``: DocumentChunk).
    from context_assembler import ContextAssembler
    from generation_pipeline import MedicalGenerationPipeline
    from llm_generator import LLMGenerator

    assembler = ContextAssembler(tokenizer_name=None)
    llm = LLMGenerator(
        model_name=boot.OLLAMA_MODEL,
        base_url=boot.OLLAMA_BASE_URL,
        timeout=timeout,
    )

    # 2) Switch to stage05 ``models`` (EntityMatch/EnhancedQuery) before 06 loads
    #    its enhancer. 05 and 07 both ship a top-level ``models`` module, so we
    #    must drop the cached stage07 one and re-prioritize stage05 ``src``.
    stage05_src = str((stage06.parent / "05 检索系统开发第一部分" / "src").resolve())
    if stage05_src in sys.path:
        sys.path.remove(stage05_src)
    sys.path.insert(0, stage05_src)
    for name in ("models", "medical_patterns", "query_enhancer"):
        sys.modules.pop(name, None)

    from pipeline import RetrievalPipeline

    retrieval = RetrievalPipeline.from_mode(
        "full",
        fusion_strategy=fusion_strategy,
        skip_rerank=skip_rerank,
        load_reranker=not skip_rerank,
    )

    generation_pipe = MedicalGenerationPipeline(
        retrieval_pipeline=retrieval,
        context_assembler=assembler,
        llm_generator=llm,
        skip_evidence_eval=skip_evidence_eval,
        skip_critical_review=skip_critical_review,
        max_context_tokens=max_context_tokens,
    )
    return generation_pipe, str(boot.OLLAMA_MODEL)


def resolve_context_text(generation_pipeline: Any, query: str) -> str:
    """Assemble context once for cache key alignment (live full mode)."""
    retrieval_result = generation_pipeline.retrieval_pipeline.run(query)
    candidates = retrieval_result.get("reranked") or retrieval_result.get("retrieval", {}).get("fused", [])
    assembled = generation_pipeline.context_assembler.assemble(
        candidates,
        max_context_tokens=generation_pipeline.max_context_tokens,
    )
    return assembled.context_text


def build_pipeline_with_eval_live_full(
    stage06: Path,
    stage07: Path,
    stage08: Path,
    *,
    skip_evidence_eval: bool = True,
    skip_critical_review: bool = True,
    max_context_tokens: int = 1200,
    timeout: float = 180.0,
    skip_rerank: bool = False,
    cache_ttl_seconds: int = 86400,
) -> tuple[Any, Any, str]:
    from answer_evaluator import AnswerEvaluator
    from generation_cache import GenerationCache
    from pipeline_with_eval import PipelineWithEval

    generation_pipe, model_name = build_live_full_generation_pipeline(
        stage06,
        stage07,
        stage08,
        skip_evidence_eval=skip_evidence_eval,
        skip_critical_review=skip_critical_review,
        max_context_tokens=max_context_tokens,
        timeout=timeout,
        skip_rerank=skip_rerank,
    )
    pipe = PipelineWithEval.from_pipeline(
        generation_pipe,
        evaluator=AnswerEvaluator(),
        cache=GenerationCache(ttl_seconds=cache_ttl_seconds),
        provider="stage09_live_full",
        model_name=model_name,
    )
    return pipe, generation_pipe, model_name


def run_live_full_eval_task(
    pipe_eval: Any,
    generation_pipeline: Any,
    query: str,
    ground_truth_entry: dict[str, Any],
    *,
    use_cache: bool = True,
    force_refresh: bool = False,
    temperature: float = 0.2,
    model_name: str = "",
) -> dict[str, Any]:
    started = time.perf_counter()
    context_text = resolve_context_text(generation_pipeline, query)
    result = pipe_eval.run_with_cache_and_eval(
        query,
        ground_truth_entry=ground_truth_entry,
        use_cache=use_cache,
        force_refresh=force_refresh,
        context_text=context_text,
        temperature=temperature,
        model_name=model_name,
        extensions={"context_chars": len(context_text), "retrieval_mode": "full"},
    )
    result["latency_seconds"] = round(time.perf_counter() - started, 4)
    result["status"] = "ok"
    return result


def build_full_eval_report(
    *,
    mode: str,
    config: dict[str, Any],
    first_pass: list[dict[str, Any]],
    second_pass: list[dict[str, Any]] | None = None,
    batch_stats: dict[str, Any] | None = None,
    retrieval_mode: str = "full",
    eval_subset: str = "full_corpus",
) -> dict[str, Any]:
    from report_builder import build_eval_cache_batch_report

    report = build_eval_cache_batch_report(
        mode=mode,
        config=config,
        first_pass=first_pass,
        second_pass=second_pass,
        batch_stats=batch_stats,
    )
    report["retrieval_mode"] = retrieval_mode
    report["eval_subset"] = eval_subset
    report["corpus_size_hint"] = CORPUS_SIZE_HINT
    report.setdefault("extensions", {})
    report["extensions"].update(
        {
            "notebook": "answer-eval-cache-batch-full.ipynb",
            "stage": "stage09_phase7",
        }
    )
    return report


def compare_eval_reports(sample_report_path: Path, full_report_path: Path) -> dict[str, Any]:
    if not sample_report_path.is_file():
        raise FileNotFoundError(sample_report_path)
    if not full_report_path.is_file():
        raise FileNotFoundError(full_report_path)

    sample = json.loads(sample_report_path.read_text(encoding="utf-8"))
    full = json.loads(full_report_path.read_text(encoding="utf-8"))
    sample_by_query = {item["query"]: item for item in sample.get("first_pass", [])}
    full_by_query = {item["query"]: item for item in full.get("first_pass", [])}

    per_query: list[dict[str, Any]] = []
    for query in sorted(set(sample_by_query) | set(full_by_query)):
        s_item = sample_by_query.get(query, {})
        f_item = full_by_query.get(query, {})
        s_eval = s_item.get("evaluation") or {}
        f_eval = f_item.get("evaluation") or {}
        per_query.append(
            {
                "query": query,
                "sample_rouge1": (s_eval.get("rouge") or {}).get("rouge1"),
                "full_rouge1": (f_eval.get("rouge") or {}).get("rouge1"),
                "sample_key_info_recall": s_eval.get("key_info_recall"),
                "full_key_info_recall": f_eval.get("key_info_recall"),
                "sample_hallucination_risk": s_eval.get("hallucination_risk"),
                "full_hallucination_risk": f_eval.get("hallucination_risk"),
                "sample_latency_seconds": s_item.get("latency_seconds"),
                "full_latency_seconds": f_item.get("latency_seconds"),
            }
        )

    s_summary = sample.get("summary", {}).get("evaluation_first_pass", {})
    f_summary = full.get("summary", {}).get("evaluation_first_pass", {})
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sample_report": str(sample_report_path),
        "full_report": str(full_report_path),
        "summary": {
            "sample": s_summary,
            "full": f_summary,
            "delta": {
                "rouge1_avg": round(
                    float(f_summary.get("rouge1_avg", 0.0)) - float(s_summary.get("rouge1_avg", 0.0)),
                    4,
                ),
                "key_info_recall_avg": round(
                    float(f_summary.get("key_info_recall_avg", 0.0))
                    - float(s_summary.get("key_info_recall_avg", 0.0)),
                    4,
                ),
            },
        },
        "per_query": per_query,
    }


def save_json(path: Path, payload: dict[str, Any] | list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _ensure_stage05_src(stage06: Path) -> str:
    stage05_src = str((stage06.parent / "05 检索系统开发第一部分" / "src").resolve())
    if stage05_src in sys.path:
        sys.path.remove(stage05_src)
    sys.path.insert(0, stage05_src)
    for name in ("models", "medical_patterns", "query_enhancer"):
        sys.modules.pop(name, None)
    return stage05_src


def _ensure_stage06_src(stage06: Path) -> str:
    stage06_src = str((stage06 / "src").resolve())
    if stage06_src in sys.path:
        sys.path.remove(stage06_src)
    sys.path.insert(0, stage06_src)
    for name in ("config", "bm25_index", "bm25_sharded"):
        sys.modules.pop(name, None)
    return stage06_src


def _overlap_stats(ids_a: list[str], ids_b: list[str], top_k: int) -> dict[str, Any]:
    set_a, set_b = set(ids_a), set(ids_b)
    inter = set_a & set_b
    union = set_a | set_b
    return {
        "top_k": top_k,
        "overlap_count": len(inter),
        "overlap_rate": round(len(inter) / top_k, 4) if top_k else 0.0,
        "jaccard": round(len(inter) / len(union), 4) if union else 1.0,
        "only_in_a": sorted(set_a - set_b),
        "only_in_b": sorted(set_b - set_a),
        "shared": sorted(inter),
    }


def compare_bm25_sharded_vs_mono(
    stage06: Path,
    queries: list[str],
    *,
    top_k: int = 10,
    sample_shard_size: int = 400,
    full_cache_dir: Path | None = None,
    include_full: bool = True,
) -> dict[str, Any]:
    """对比分片 BM25 与单体 BM25 的 keyword top-k 重叠率。

    返回两组结果：
    - ``controlled_same_corpus``：同一样本语料（隔离分片近似误差）
    - ``full_sharded_vs_sample_mono``：全量分片 vs 样本单体（工程切换视角）
    """
    import tempfile

    _ensure_stage06_src(stage06)
    _ensure_stage05_src(stage06)

    from bm25_index import BM25Index  # type: ignore[import-not-found]
    from bm25_sharded import ShardedBM25Index, build_sharded_bm25  # type: ignore[import-not-found]
    from config import resolve_bm25_cache_dir, resolve_chunks_path  # type: ignore[import-not-found]
    from query_enhancer import MedicalQueryEnhancer  # type: ignore[import-not-found]

    enhancer = MedicalQueryEnhancer()
    sample_jsonl = resolve_chunks_path("sample")

    def _keyword_ids(bm25_index: Any, query: str) -> list[str]:
        enhanced = enhancer.process(query)
        hits = bm25_index.search(enhanced.keyword_query, top_k=top_k)
        return [str(h["chunk_id"]) for h in hits]

    mono_sample = BM25Index()
    mono_sample.build_from_jsonl(sample_jsonl)

    with tempfile.TemporaryDirectory(prefix="bm25_shard_sample_") as tmp:
        build_sharded_bm25(
            sample_jsonl,
            tmp,
            shard_size=sample_shard_size,
            resume=False,
        )
        shard_sample = ShardedBM25Index(tmp)

        controlled_rows: list[dict[str, Any]] = []
        for query in queries:
            mono_ids = _keyword_ids(mono_sample, query)
            shard_ids = _keyword_ids(shard_sample, query)
            stats = _overlap_stats(mono_ids, shard_ids, top_k)
            controlled_rows.append(
                {
                    "query": query,
                    "keyword_query": enhancer.process(query).keyword_query,
                    "mono_top_k": mono_ids,
                    "sharded_top_k": shard_ids,
                    **stats,
                }
            )

    controlled_summary = {
        "corpus": "sample",
        "corpus_chunks": mono_sample.size,
        "sample_shard_size": sample_shard_size,
        "avg_overlap_rate": round(
            sum(r["overlap_rate"] for r in controlled_rows) / max(len(controlled_rows), 1),
            4,
        ),
        "avg_jaccard": round(
            sum(r["jaccard"] for r in controlled_rows) / max(len(controlled_rows), 1),
            4,
        ),
    }

    full_rows: list[dict[str, Any]] = []
    full_summary: dict[str, Any] = {"ready": False}
    if include_full:
        cache_dir = full_cache_dir or resolve_bm25_cache_dir("full")
        if cache_dir is not None and ShardedBM25Index.is_sharded(cache_dir):
            shard_full = ShardedBM25Index(cache_dir)
            for query in queries:
                mono_ids = _keyword_ids(mono_sample, query)
                full_ids = _keyword_ids(shard_full, query)
                stats = _overlap_stats(mono_ids, full_ids, top_k)
                full_rows.append(
                    {
                        "query": query,
                        "keyword_query": enhancer.process(query).keyword_query,
                        "sample_mono_top_k": mono_ids,
                        "full_sharded_top_k": full_ids,
                        **stats,
                    }
                )
            full_summary = {
                "ready": True,
                "corpus": "full_sharded_vs_sample_mono",
                "full_chunks": shard_full.size,
                "full_num_shards": shard_full.num_shards,
                "cache_dir": str(cache_dir),
                "avg_overlap_rate": round(
                    sum(r["overlap_rate"] for r in full_rows) / max(len(full_rows), 1),
                    4,
                ),
                "avg_jaccard": round(
                    sum(r["jaccard"] for r in full_rows) / max(len(full_rows), 1),
                    4,
                ),
                "note": "语料规模不同，重叠率低是预期现象，不代表分片近似失效",
            }
        else:
            full_summary["message"] = "full sharded BM25 cache not ready (run C2.5 first)"
    else:
        full_summary["message"] = "skipped (include_full=False)"

    return {
        "top_k": top_k,
        "controlled_same_corpus": {
            "summary": controlled_summary,
            "per_query": controlled_rows,
        },
        "full_sharded_vs_sample_mono": {
            "summary": full_summary,
            "per_query": full_rows,
        },
    }
