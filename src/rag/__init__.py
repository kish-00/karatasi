from src.rag.answers import generate_answer
from src.rag.context import build_context
from src.rag.retriever import LEASE_FILE, is_lease_question, retrieve

DEFAULT_MAX_CHUNKS = 8
DEFAULT_MAX_CONTEXT_CHARS = 4000


def answer_semantic(
    store,
    question: str,
    *,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> tuple[list[str], str] | None:
    chunks = retrieve(store, question, k=max_chunks)[:max_chunks]
    if not chunks:
        return None
    context = build_context(chunks, max_chars=max_chars)
    if is_lease_question(question):
        files = [LEASE_FILE]
    else:
        files = list(dict.fromkeys(c["file"] for c in chunks))
    text = generate_answer(question, context)
    if not text:
        text = chunks[0]["text"]
    return files, text


__all__ = ["answer_semantic"]
