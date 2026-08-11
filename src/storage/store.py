"""FinanceStore — typed access to the SME Brief SQLite database.

Structured financial records answer deterministic SQL questions;
vector chunks answer semantic questions. Both live in one file.

The public surface here is the contract the ingest pipeline, query
router, app, and eval harness build against. If we ever move to
Postgres/pgvector, this class is the seam.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import sqlite_vec

from src.storage.db import connect, default_db_path

logger = logging.getLogger(__name__)


class FinanceStore:
    """SQLite-backed document + finance + vector store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path else default_db_path()
        self._lock = Lock()
        self._conn: sqlite3.Connection | None = None

    # ── Connection ─────────────────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect(self._path)
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def run_sql(self, sql: str, params: tuple | list = ()) -> list[dict]:
        """Run arbitrary SQL and return rows as dicts (safe: parameters bound)."""
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]
            self.conn.commit()
            return rows

    # ── Documents ──────────────────────────────────────────────────

    def upsert_document(
        self,
        file: str,
        *,
        doc_type: str,
        lang: str = "unknown",
        date: str | None = None,
        page_count: int = 1,
        ocr_pages: int = 0,
    ) -> int:
        """Get or create a document row by filename; returns doc_id."""
        with self._lock:
            cur = self.conn.execute(
                "SELECT id FROM documents WHERE file = ?", (file,)
            )
            row = cur.fetchone()
            if row is not None:
                self.conn.execute(
                    """
                    UPDATE documents SET doc_type=?, lang=?, date=?, page_count=?,
                        ocr_pages=? WHERE id=?
                    """,
                    (doc_type, lang, date, page_count, ocr_pages, row["id"]),
                )
                self.conn.commit()
                return int(row["id"])
            cur = self.conn.execute(
                """
                INSERT INTO documents (file, doc_type, lang, date, page_count, ocr_pages)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (file, doc_type, lang, date, page_count, ocr_pages),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def delete_document(self, file: str) -> None:
        with self._lock:
            self.conn.execute(
                """
                DELETE FROM vec_chunks WHERE rowid IN (
                    SELECT c.id FROM chunks c JOIN documents d ON c.doc_id = d.id
                    WHERE d.file = ?
                )
                """,
                (file,),
            )
            self.conn.execute("DELETE FROM documents WHERE file = ?", (file,))
            self.conn.commit()

    def delete_all(self) -> None:
        with self._lock:
            for table in (
                "vec_chunks",
                "chunks",
                "statement_entries",
                "statements",
                "contracts",
                "receipts",
                "invoices",
                "documents",
            ):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.commit()

    def list_documents(self) -> list[dict]:
        return self.run_sql(
            """
            SELECT d.id, d.file, d.doc_type, d.lang, d.date, d.page_count,
                   d.ocr_pages, d.ingested_at,
                   (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.id) AS n_chunks
            FROM documents d ORDER BY d.file
            """
        )

    def count_documents(self) -> int:
        row = self.run_sql("SELECT COUNT(*) AS n FROM documents")
        return int(row[0]["n"]) if row else 0

    def max_doc_date(self) -> str | None:
        """Most recent document date (used to resolve 'this quarter')."""
        rows = self.run_sql(
            "SELECT MAX(date) AS d FROM documents WHERE date IS NOT NULL"
        )
        return rows[0]["d"] if rows and rows[0]["d"] else None

    # ── Structured financial rows ───────────────────────────────────

    def set_invoice(self, doc_id: int, **fields: Any) -> None:
        allowed = {
            "number", "date", "supplier", "buyer", "currency", "amount",
            "vat", "vat_rate", "total", "paid", "paid_date", "payment_terms",
        }
        self._set_structured("invoices", doc_id, fields, allowed)

    def set_receipt(self, doc_id: int, **fields: Any) -> None:
        allowed = {"number", "date", "amount", "currency", "from_name"}
        self._set_structured("receipts", doc_id, fields, allowed)

    def set_contract(
        self, doc_id: int, contract_type: str, clauses: dict[str, Any]
    ) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM contracts WHERE doc_id = ?", (doc_id,))
            self.conn.execute(
                """
                INSERT INTO contracts (doc_id, contract_type, clauses)
                VALUES (?, ?, ?)
                """,
                (doc_id, contract_type, json.dumps(clauses, ensure_ascii=False)),
            )
            self.conn.commit()

    def set_statement(
        self,
        doc_id: int,
        supplier: str,
        period: str,
        entries: list[dict[str, Any]],
    ) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM statements WHERE doc_id = ?", (doc_id,))
            cur = self.conn.execute(
                "INSERT INTO statements (doc_id, supplier, period) VALUES (?, ?, ?)",
                (doc_id, supplier, period),
            )
            sid = cur.lastrowid
            for e in entries:
                self.conn.execute(
                    """
                    INSERT INTO statement_entries (statement_id, date, ref, amount, kind)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (sid, e.get("date"), e.get("ref"), e.get("amount"), e.get("kind")),
                )
            self.conn.commit()

    def _set_structured(
        self,
        table: str,
        doc_id: int,
        fields: dict[str, Any],
        allowed: set[str],
    ) -> None:
        cols = [c for c in allowed if c in fields and fields[c] is not None]
        with self._lock:
            self.conn.execute(f"DELETE FROM {table} WHERE doc_id = ?", (doc_id,))
            if cols:
                sql = (
                    f"INSERT INTO {table} (doc_id, {', '.join(cols)}) "
                    f"VALUES (?, {', '.join('?' for _ in cols)})"
                )
                self.conn.execute(sql, [doc_id, *[fields[c] for c in cols]])
            self.conn.commit()

    # ── Chunks + vectors ────────────────────────────────────────────

    def add_chunks(
        self,
        doc_id: int,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        """Insert chunk rows and their embeddings (must be same length)."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        with self._lock:
            for chunk, emb in zip(chunks, embeddings):
                cur = self.conn.execute(
                    """
                    INSERT INTO chunks (doc_id, page, chunk_idx, lang, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        chunk["page"],
                        chunk.get("chunk_idx", 0),
                        chunk.get("lang", "unknown"),
                        chunk["text"],
                    ),
                )
                vec_blob = sqlite_vec.serialize_float32(np.asarray(emb, dtype=np.float32))
                self.conn.execute(
                    "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                    (cur.lastrowid, vec_blob),
                )
            self.conn.commit()

    def vector_search(self, query_vec: list[float], k: int = 5) -> list[dict]:
        """Cosine kNN over chunk embeddings; returns enriched chunk dicts."""
        q = sqlite_vec.serialize_float32(np.asarray(query_vec, dtype=np.float32))
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT v.rowid AS chunk_id, v.distance
                FROM vec_chunks v
                WHERE v.embedding MATCH ? AND k = ?
                """,
                (q, int(k)),
            ).fetchall()
            if not rows:
                return []
            ids = [r["chunk_id"] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            chunks = self.conn.execute(
                f"""
                SELECT c.id, c.page, c.chunk_idx, c.lang, c.text,
                       d.file, d.doc_type, d.date
                FROM chunks c JOIN documents d ON c.doc_id = d.id
                WHERE c.id IN ({placeholders})
                """,
                ids,
            ).fetchall()
            by_id = {c["id"]: c for c in chunks}
            out: list[dict] = []
            for r in rows:
                c = by_id.get(r["chunk_id"])
                if c is None:
                    continue
                out.append(
                    {
                        "text": c["text"],
                        "page": c["page"],
                        "file": c["file"],
                        "doc_type": c["doc_type"],
                        "lang": c["lang"],
                        "date": c["date"],
                        "distance": float(r["distance"]),
                    }
                )
            return out


# ── Singleton ────────────────────────────────────────────────────────

_store: FinanceStore | None = None
_store_lock = Lock()


def get_store(db_path: str | Path | None = None) -> FinanceStore:
    """Get the process-wide FinanceStore singleton."""
    global _store  # noqa: PLW0603
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = FinanceStore(db_path)
    return _store
