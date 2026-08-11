"""Ingest pipeline: synthetic corpus → FinanceStore (SQLite + sqlite-vec).

Loads every document in data/synthetic/manifest.json into the store:
structured financial rows (invoices, receipts, contracts, statements)
plus per-page text chunks with 384-dim multilingual-e5-small embeddings.
"""

from src.ingest.ingest import (
    DEFAULT_DB,
    DEFAULT_DOCS,
    DEFAULT_MANIFEST,
    ingest_manifest,
)

__all__ = [
    "DEFAULT_DB",
    "DEFAULT_DOCS",
    "DEFAULT_MANIFEST",
    "ingest_manifest",
]
