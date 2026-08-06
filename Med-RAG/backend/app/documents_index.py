"""Build documents_{sample,full}.sqlite from oa_comm_slim (logical batches + resume).

Layout under ``Dataset/documents/`` (sample / full 分目录，避免混放)::

    documents/
    ├── README.md
    ├── sample/
    │   ├── documents_sample.sqlite
    │   ├── progress_sample.json
    │   └── manifest_sample.json
    └── full/
        ├── documents_full.sqlite
        ├── progress_full.json
        └── manifest_full.json
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

SCHEMA_VERSION = 1
FORMAT = "documents_index_v1"
Mode = Literal["sample", "full"]

DDL = """
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
CREATE INDEX IF NOT EXISTS idx_documents_journal ON documents(journal);
CREATE INDEX IF NOT EXISTS idx_documents_pub_year ON documents(pub_year);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dataset_paths():
    from dataset_paths import (  # type: ignore
        CHUNKS_SAMPLE_JSONL,
        DOCUMENTS_DIR,
        DOCUMENTS_FULL_DIR,
        DOCUMENTS_FULL_SQLITE,
        DOCUMENTS_SAMPLE_DIR,
        DOCUMENTS_SAMPLE_SQLITE,
        SLIM_JSONL,
    )

    return {
        "slim": SLIM_JSONL,
        "chunks_sample": CHUNKS_SAMPLE_JSONL,
        "dir": DOCUMENTS_DIR,
        "sample_dir": DOCUMENTS_SAMPLE_DIR,
        "full_dir": DOCUMENTS_FULL_DIR,
        "sample_sqlite": DOCUMENTS_SAMPLE_SQLITE,
        "full_sqlite": DOCUMENTS_FULL_SQLITE,
    }


def mode_dir_for(mode: Mode) -> Path:
    paths = _dataset_paths()
    return paths["sample_dir"] if mode == "sample" else paths["full_dir"]


def sqlite_path_for(mode: Mode) -> Path:
    paths = _dataset_paths()
    return paths["sample_sqlite"] if mode == "sample" else paths["full_sqlite"]


def progress_path_for(mode: Mode) -> Path:
    return mode_dir_for(mode) / f"progress_{mode}.json"


def manifest_path_for(mode: Mode) -> Path:
    return mode_dir_for(mode) / f"manifest_{mode}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_sig(source: Path) -> dict[str, Any]:
    if not source.is_file():
        return {"source_path": str(source), "source_exists": False}
    st = source.stat()
    return {
        "source_path": str(source.resolve()),
        "source_exists": True,
        "source_size_bytes": st.st_size,
        "source_mtime": st.st_mtime,
    }


def load_sample_pmcids(chunks_path: Path | None = None) -> set[str]:
    path = chunks_path or _dataset_paths()["chunks_sample"]
    if not path.is_file():
        raise FileNotFoundError(f"chunks_sample not found: {path}")
    ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            doc_id = row.get("doc_id") or row.get("pmcid")
            if doc_id:
                ids.add(str(doc_id))
    return ids


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()


def _row_from_slim(rec: dict[str, Any], updated_at: str) -> tuple[Any, ...] | None:
    pmcid = rec.get("pmcid")
    if not pmcid:
        return None
    pub_year = rec.get("pub_year")
    try:
        pub_year_i = int(pub_year) if pub_year is not None and pub_year != "" else None
    except (TypeError, ValueError):
        pub_year_i = None
    n_chars = rec.get("n_chars_abstract")
    try:
        n_chars_i = int(n_chars) if n_chars is not None and n_chars != "" else None
    except (TypeError, ValueError):
        n_chars_i = None
    return (
        str(pmcid),
        str(rec["pmid"]) if rec.get("pmid") is not None else None,
        rec.get("title"),
        rec.get("abstract"),
        rec.get("journal"),
        pub_year_i,
        rec.get("pub_date"),
        n_chars_i,
        SCHEMA_VERSION,
        updated_at,
    )


_UPSERT_SQL = """
INSERT OR REPLACE INTO documents (
    pmcid, pmid, title, abstract, journal, pub_year, pub_date,
    n_chars_abstract, schema_version, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def status(mode: Mode) -> dict[str, Any]:
    """Build/status snapshot for CLI / notebook."""
    sqlite_path = sqlite_path_for(mode)
    progress = _read_json(progress_path_for(mode)) or {}
    manifest = _read_json(manifest_path_for(mode)) or {}
    row_count = None
    if sqlite_path.is_file():
        try:
            with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as conn:
                row_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        except sqlite3.Error:
            row_count = None
    return {
        "mode": mode,
        "sqlite": str(sqlite_path),
        "sqlite_exists": sqlite_path.is_file(),
        "row_count": row_count,
        "progress": progress,
        "manifest": manifest,
        "completed": manifest.get("status") == "completed",
    }


def build_documents_index(
    mode: Mode = "sample",
    *,
    batch_size: int = 50_000,
    resume: bool = True,
    limit: int | None = None,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
    slim_path: Path | None = None,
    chunks_sample_path: Path | None = None,
) -> dict[str, Any]:
    """Stream slim → sqlite with batch commit + progress_{mode}.json resume."""
    paths = _dataset_paths()
    slim = Path(slim_path) if slim_path else paths["slim"]
    if not slim.is_file():
        raise FileNotFoundError(f"slim JSONL not found: {slim}")

    out_dir = mode_dir_for(mode)
    out_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = sqlite_path_for(mode)
    prog_path = progress_path_for(mode)
    man_path = manifest_path_for(mode)

    allow_pmcids: set[str] | None = None
    if mode == "sample":
        allow_pmcids = load_sample_pmcids(chunks_sample_path)
        if not allow_pmcids:
            raise ValueError("sample mode: empty pmcid set from chunks_sample")

    sig = _source_sig(slim)
    skip_lines = 0
    valid_rows = 0
    if resume:
        prev = _read_json(prog_path)
        if (
            prev
            and prev.get("format") == FORMAT
            and prev.get("mode") == mode
            and prev.get("schema_version") == SCHEMA_VERSION
            and prev.get("batch_size") == batch_size
            and prev.get("source_path") == sig.get("source_path")
            and prev.get("source_mtime") == sig.get("source_mtime")
            and sqlite_path.is_file()
        ):
            skip_lines = int(prev.get("processed_lines", 0))
            valid_rows = int(prev.get("valid_rows", 0))

    if not resume or skip_lines == 0:
        if sqlite_path.exists():
            sqlite_path.unlink()
        skip_lines = 0
        valid_rows = 0

    t0 = time.perf_counter()
    conn = sqlite3.connect(str(sqlite_path))
    try:
        _ensure_schema(conn)
        buffer: list[tuple[Any, ...]] = []
        line_no = 0
        last_pmcid: str | None = None
        found: set[str] = set()

        def flush() -> None:
            nonlocal buffer, valid_rows
            if not buffer:
                return
            conn.executemany(_UPSERT_SQL, buffer)
            conn.commit()
            valid_rows += len(buffer)
            buffer = []

        def emit(extra: dict[str, Any] | None = None) -> None:
            payload = {
                "format": FORMAT,
                "mode": mode,
                "schema_version": SCHEMA_VERSION,
                "batch_size": batch_size,
                "processed_lines": line_no,
                "valid_rows": valid_rows,
                "last_pmcid": last_pmcid,
                "matched_sample": len(found) if allow_pmcids is not None else None,
                "sample_target": len(allow_pmcids) if allow_pmcids is not None else None,
                "updated_at": _now_iso(),
                **sig,
            }
            if extra:
                payload.update(extra)
            _write_json(prog_path, payload)
            if progress_cb:
                progress_cb(payload)

        with slim.open(encoding="utf-8") as f:
            for raw in f:
                line_no += 1
                if line_no <= skip_lines:
                    continue
                raw = raw.strip()
                if not raw:
                    continue
                rec = json.loads(raw)
                pmcid = rec.get("pmcid")
                if not pmcid:
                    continue
                pmcid_s = str(pmcid)
                if allow_pmcids is not None:
                    if pmcid_s not in allow_pmcids or pmcid_s in found:
                        continue

                row = _row_from_slim(rec, _now_iso())
                if row is None:
                    continue
                buffer.append(row)
                last_pmcid = row[0]
                if allow_pmcids is not None:
                    found.add(pmcid_s)

                if len(buffer) >= batch_size:
                    flush()
                    emit({"phase": "writing"})

                if limit is not None and valid_rows + len(buffer) >= limit:
                    break

                if allow_pmcids is not None and len(found) >= len(allow_pmcids):
                    flush()
                    emit({"phase": "sample_complete"})
                    break

            flush()
            emit({"phase": "finalizing"})

        elapsed = time.perf_counter() - t0
        # Actual count from DB
        db_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        manifest = {
            "format": FORMAT,
            "status": "completed",
            "mode": mode,
            "schema_version": SCHEMA_VERSION,
            "batch_size": batch_size,
            "row_count": db_count,
            "valid_rows_written": valid_rows,
            "processed_lines": line_no,
            "elapsed_sec": round(elapsed, 3),
            "built_at": _now_iso(),
            "builder": "app.documents_index.build_documents_index",
            "sample_pmcid_target": len(allow_pmcids) if allow_pmcids else None,
            **sig,
        }
        _write_json(man_path, manifest)
        emit({"phase": "completed", "status": "completed", "row_count": db_count})
        return manifest
    finally:
        conn.close()
