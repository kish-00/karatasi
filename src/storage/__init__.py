"""Storage layer: SQLite + sqlite-vec for SME Brief.

One file, one process, ACID — structured financial rows and vector
chunks live in the same database. Zero daemons, fully offline.
"""

from src.storage.store import FinanceStore, get_store

__all__ = ["FinanceStore", "get_store"]
