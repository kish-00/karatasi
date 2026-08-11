"""Shared embedding helpers — multilingual-e5-small, offline, 384-dim.

Both the ingest pipeline (passage embeddings) and the query router
(query embeddings) load the model through here so the
SentenceTransformer instance is created exactly once per process.

multilingual-e5 recommends prefixing inputs: passages with
"passage: " and queries with "query: " (improves retrieval quality).
The storage layer is prefix-agnostic — it stores plain float vectors.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # repo root
MODEL_DIR = BASE / "models" / "multilingual-e5-small"

_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


@lru_cache(maxsize=1)
def get_model():
    """Load (or return the cached) SentenceTransformer, offline only."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(str(MODEL_DIR), local_files_only=True)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks with the e5 passage prefix (order preserved)."""
    if not texts:
        return []
    model = get_model()
    vecs = model.encode(
        [_PASSAGE_PREFIX + t for t in texts],
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    """Embed a single user query with the e5 query prefix."""
    model = get_model()
    vec = model.encode(_QUERY_PREFIX + text, normalize_embeddings=True)
    return vec.tolist()
