"""SQLite schema + connection management for SME Brief.

Design goals:
- One file, one process, ACID (no daemon — fits the offline 8GB laptop).
- Structured financial rows (invoices, receipts, contracts, statements)
  answer numeric/temporal questions with deterministic SQL.
- Chunks + float32 embeddings live beside them; kNN search runs on the
  sqlite-vec virtual table (vec0).
- Storage engine is swappable: the same SQL schema ports to
  Postgres/pgvector via the FinanceStore interface (see docs/TECH_STACK.md).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import sqlite_vec

logger = logging.getLogger(__name__)

_DB_FILENAME = "smebrief.db"
_EMBED_DIMS = 384  # multilingual-e5-small

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    file        TEXT UNIQUE NOT NULL,
    doc_type    TEXT NOT NULL,               -- invoice | receipt | contract | statement | other
    lang        TEXT NOT NULL DEFAULT 'unknown',
    date        TEXT,                        -- ISO YYYY-MM-DD or NULL
    page_count  INTEGER NOT NULL DEFAULT 1,
    ocr_pages   INTEGER NOT NULL DEFAULT 0,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoices (
    id            INTEGER PRIMARY KEY,
    doc_id        INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    number        TEXT,
    date          TEXT,
    supplier      TEXT,
    buyer         TEXT,
    currency      TEXT,
    amount        REAL,                       -- subtotal
    vat           REAL,
    vat_rate      REAL,
    total         REAL,
    paid          INTEGER NOT NULL DEFAULT 0, -- 0/1
    paid_date     TEXT,
    payment_terms TEXT
);

CREATE TABLE IF NOT EXISTS receipts (
    id        INTEGER PRIMARY KEY,
    doc_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    number    TEXT,
    date      TEXT,
    amount    REAL,
    currency  TEXT,
    from_name TEXT
);

CREATE TABLE IF NOT EXISTS contracts (
    id            INTEGER PRIMARY KEY,
    doc_id        INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    contract_type TEXT,
    clauses       TEXT                        -- JSON dict of extracted clauses
);

CREATE TABLE IF NOT EXISTS statements (
    id       INTEGER PRIMARY KEY,
    doc_id   INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    supplier TEXT,
    period   TEXT
);

CREATE TABLE IF NOT EXISTS statement_entries (
    id           INTEGER PRIMARY KEY,
    statement_id INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    date         TEXT,
    ref          TEXT,
    amount       REAL,
    kind         TEXT                         -- invoice | payment
);

CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY,
    doc_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page      INTEGER NOT NULL,
    chunk_idx INTEGER NOT NULL,
    lang      TEXT,
    text      TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with the schema applied and vec loaded."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.executescript(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
            embedding float[{_EMBED_DIMS}] distance_metric=cosine
        );
        """
    )
    return conn


def default_db_path() -> Path:
    """Repository data dir: <repo>/data/smebrief.db"""
    return Path(__file__).resolve().parents[2] / "data" / _DB_FILENAME
