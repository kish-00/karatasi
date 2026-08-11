from __future__ import annotations

from src.embeddings import embed_query

LEASE_FILE = "contrat_bail_entrepot.pdf"
LEASE_MARKERS = ("bail", "entrepôt", "entrepot", "warehouse", "lease", "location")

CHUNK_COLS = "c.id, c.page, c.chunk_idx, c.lang, c.text, d.file, d.doc_type, d.date"


def is_lease_question(question: str) -> bool:
    ql = question.lower()
    return any(marker in ql for marker in LEASE_MARKERS)


def retrieve(store, question: str, k: int = 8) -> list[dict]:
    if is_lease_question(question):
        return store.run_sql(
            f"SELECT {CHUNK_COLS} FROM chunks c JOIN documents d ON c.doc_id = d.id "
            "WHERE d.file = ? ORDER BY c.page, c.chunk_idx",
            (LEASE_FILE,),
        )
    return store.vector_search(embed_query(question), k=k)
