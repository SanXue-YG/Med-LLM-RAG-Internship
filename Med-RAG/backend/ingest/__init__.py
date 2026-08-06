"""Minimal ingest pipeline for Med-RAG demo (XML / slim JSONL → chunks → Chroma).

Self-contained under ``Med-RAG/backend/ingest`` + ``Med-RAG/data/``.
Incremental strategy (demo):
  - append new chunks to ``data/processed/chunks_sample.jsonl``
  - Chroma ``collection.add`` (ids = chunk_id; duplicates skipped)
  - documents sqlite upsert when abstract/title available
  - BM25: sample mode rebuilds in-memory at query time; mark pending for full
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import (
    CHROMA_SAMPLE_DIR,
    CHUNKS_SAMPLE_JSONL,
    COLLECTION_SAMPLE,
    DOCUMENTS_SAMPLE_SQLITE,
    RAW_UPLOADS_DIR,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    RAW_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_SAMPLE_JSONL.parent.mkdir(parents=True, exist_ok=True)
    CHROMA_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_SAMPLE_SQLITE.parent.mkdir(parents=True, exist_ok=True)


def save_upload(filename: str, content: bytes) -> Path:
    _ensure_dirs()
    safe = "".join(c for c in Path(filename).name if c.isalnum() or c in "._-")
    if not safe:
        safe = "upload.bin"
    dest = RAW_UPLOADS_DIR / f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe}"
    dest.write_bytes(content)
    return dest


def _parse_xml_file(path: Path) -> dict[str, Any] | None:
    from ingest.parse_pmc import parse_pmc_xml, record_for_jsonl

    rec = parse_pmc_xml(path)
    if not rec:
        return None
    return record_for_jsonl(rec, slim=True)


def _load_jsonl_docs(path: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))
    return docs


def _docs_from_upload(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".xml":
        doc = _parse_xml_file(path)
        return [doc] if doc else []
    if suffix in {".jsonl", ".json"}:
        if suffix == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return list(raw)
            if isinstance(raw, dict):
                return [raw]
            return []
        return _load_jsonl_docs(path)
    raise ValueError(f"unsupported upload type: {suffix} (use .xml / .jsonl / .json)")


def _chunk_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ingest.chunker import DocumentChunker

    chunker = DocumentChunker()
    chunks: list[dict[str, Any]] = []
    for doc in docs:
        if not doc.get("pmcid") and not doc.get("doc_id"):
            continue
        if "text" in doc and "chunk_id" in doc:
            # already a chunk record
            chunks.append(doc)
            continue
        chunks.extend(chunker.chunk_document(doc))
    return chunks


def _append_chunks_jsonl(chunks: list[dict[str, Any]]) -> int:
    CHUNKS_SAMPLE_JSONL.parent.mkdir(parents=True, exist_ok=True)
    existing_ids: set[str] = set()
    if CHUNKS_SAMPLE_JSONL.is_file():
        with CHUNKS_SAMPLE_JSONL.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_ids.add(json.loads(line).get("chunk_id", ""))
                except json.JSONDecodeError:
                    continue
    added = 0
    with CHUNKS_SAMPLE_JSONL.open("a", encoding="utf-8") as fh:
        for ch in chunks:
            cid = ch.get("chunk_id")
            if not cid or cid in existing_ids:
                continue
            fh.write(json.dumps(ch, ensure_ascii=False) + "\n")
            existing_ids.add(cid)
            added += 1
    return added


def _chroma_add_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    from ingest.embedder import DocumentEmbedder
    from ingest.index_builder import ChromaIndexBuilder, METADATA_FIELDS

    embedder = DocumentEmbedder()
    builder = ChromaIndexBuilder(
        persist_dir=CHROMA_SAMPLE_DIR,
        collection_name=COLLECTION_SAMPLE,
        embedder=embedder,
    )
    # Skip ids already present
    existing: set[str] = set()
    try:
        # Chroma get all ids can be heavy; for demo sample size is fine via peek/count
        count = builder.collection.count()
        if count > 0:
            got = builder.collection.get(include=[])
            existing = set(got.get("ids") or [])
    except Exception:
        existing = set()

    buf_ids: list[str] = []
    buf_texts: list[str] = []
    buf_metas: list[dict] = []
    for ch in chunks:
        cid = ch.get("chunk_id")
        text = ch.get("text")
        if not cid or not text or cid in existing:
            continue
        buf_ids.append(cid)
        buf_texts.append(text)
        buf_metas.append({k: ch.get(k) for k in METADATA_FIELDS if ch.get(k) is not None})

    if not buf_ids:
        return {"added": 0, "collection_count": builder.collection.count()}

    embeddings = embedder.encode_documents(buf_texts)
    builder.collection.add(
        ids=buf_ids,
        embeddings=embeddings,
        documents=buf_texts,
        metadatas=buf_metas,
    )
    return {"added": len(buf_ids), "collection_count": builder.collection.count()}


def _upsert_documents(docs: list[dict[str, Any]]) -> int:
    DOCUMENTS_SAMPLE_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DOCUMENTS_SAMPLE_SQLITE)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                pmcid TEXT PRIMARY KEY,
                pmid TEXT,
                title TEXT,
                abstract TEXT,
                journal TEXT,
                pub_year INTEGER,
                pub_date TEXT,
                n_chars_abstract INTEGER,
                schema_version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        n = 0
        for doc in docs:
            pmcid = doc.get("pmcid") or doc.get("doc_id")
            if not pmcid:
                continue
            if "chunk_id" in doc and "text" in doc and not doc.get("title"):
                continue
            con.execute(
                """
                INSERT INTO documents (
                    pmcid, pmid, title, abstract, journal, pub_year, pub_date,
                    n_chars_abstract, schema_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pmcid) DO UPDATE SET
                    pmid=excluded.pmid,
                    title=excluded.title,
                    abstract=excluded.abstract,
                    journal=excluded.journal,
                    pub_year=excluded.pub_year,
                    pub_date=excluded.pub_date,
                    n_chars_abstract=excluded.n_chars_abstract,
                    updated_at=excluded.updated_at
                """,
                (
                    str(pmcid),
                    doc.get("pmid"),
                    doc.get("title") or doc.get("source_title"),
                    doc.get("abstract"),
                    doc.get("journal"),
                    doc.get("pub_year"),
                    doc.get("pub_date"),
                    doc.get("n_chars_abstract"),
                    1,
                    _now_iso(),
                ),
            )
            n += 1
        con.commit()
        return n
    finally:
        con.close()


def run_ingest_file(path: Path) -> dict[str, Any]:
    """Ingest one uploaded file into sample indexes under Med-RAG/data/."""
    _ensure_dirs()
    t0 = time.perf_counter()
    docs = _docs_from_upload(path)
    if not docs:
        return {
            "ok": False,
            "error": "no documents parsed from upload",
            "path": str(path),
        }
    chunks = _chunk_docs(docs)
    n_jsonl = _append_chunks_jsonl(chunks)
    chroma = _chroma_add_chunks(chunks)
    n_docs = _upsert_documents(docs)
    # Invalidate lazy RAG singleton so next /qa reloads with new index
    try:
        from app.deps import reset_singletons

        reset_singletons()
    except Exception:
        pass
    return {
        "ok": True,
        "path": str(path),
        "documents_parsed": len(docs),
        "chunks_produced": len(chunks),
        "chunks_appended_jsonl": n_jsonl,
        "chroma": chroma,
        "documents_upserted": n_docs,
        "bm25_note": "sample BM25 builds in-memory from chunks_sample.jsonl on next query",
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
        "updated_at": _now_iso(),
    }


def clear_raw_uploads(*, keep_latest: int = 20) -> int:
    """Housekeeping: keep newest N uploads."""
    if not RAW_UPLOADS_DIR.is_dir():
        return 0
    files = sorted(RAW_UPLOADS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for p in files[keep_latest:]:
        if p.is_file():
            p.unlink()
            removed += 1
    return removed
