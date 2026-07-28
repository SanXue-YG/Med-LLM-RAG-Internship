"""Read-only DocumentStore over documents_{sample,full}.sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from app.documents_index import sqlite_path_for
from app.schemas.document import DocumentIn

Mode = Literal["sample", "full"]

_SELECT_COLS = "pmcid, pmid, title, abstract, journal, pub_year, pub_date"


def _row_to_doc(row: sqlite3.Row) -> DocumentIn:
    return DocumentIn(
        doc_id=row["pmcid"],
        title=row["title"] or "",
        abstract=row["abstract"],
        journal=row["journal"],
        pub_date=row["pub_date"],
        pmid=row["pmid"],
        pub_year=row["pub_year"],
    )


class DocumentStore:
    """Query literature metadata by pmcid / title keyword (read-only)."""

    def __init__(self, mode: Mode = "sample", *, sqlite_path: Path | None = None) -> None:
        self.mode: Mode = mode
        self.sqlite_path = Path(sqlite_path) if sqlite_path else sqlite_path_for(mode)

    def _connect(self) -> sqlite3.Connection:
        if not self.sqlite_path.is_file():
            raise FileNotFoundError(f"documents index missing: {self.sqlite_path}")
        conn = sqlite3.connect(f"file:{self.sqlite_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def get_document(self, doc_id: str) -> DocumentIn | None:
        """Lookup by pmcid. Returns None if missing."""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_SELECT_COLS} FROM documents WHERE pmcid = ?",
                (doc_id,),
            ).fetchone()
        return _row_to_doc(row) if row else None

    def list_documents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
    ) -> tuple[list[DocumentIn], int]:
        """Paginated list; optional title substring ``q`` (SQL LIKE)."""
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        offset = (page - 1) * page_size
        needle = (q or "").strip() or None

        with self._connect() as conn:
            if needle:
                like = f"%{needle}%"
                total = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE title LIKE ?",
                    (like,),
                ).fetchone()[0]
                rows = conn.execute(
                    f"SELECT {_SELECT_COLS} FROM documents "
                    "WHERE title LIKE ? ORDER BY pmcid LIMIT ? OFFSET ?",
                    (like, page_size, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                rows = conn.execute(
                    f"SELECT {_SELECT_COLS} FROM documents "
                    "ORDER BY pmcid LIMIT ? OFFSET ?",
                    (page_size, offset),
                ).fetchall()

        return [_row_to_doc(r) for r in rows], int(total)
