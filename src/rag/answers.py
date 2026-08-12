from __future__ import annotations

import re

from src.llm.serve import get_server

MAX_ANSWER_TOKENS = 128
MAX_ANSWER_SENTENCES = 3
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

SYSTEM_PROMPT = (
    "You are a concise financial assistant for a Senegalese SME. "
    "Answer the user's question using ONLY the documents in the context below; "
    "do not invent payment terms, amounts, or dates that are not in the documents. "
    "Answer in the same language as the question, French or English. "
    "If the documents do not contain the answer, say so in one sentence. "
    "Keep the answer to at most 3 sentences."
)

ANSWER_MARKERS = ("assistant:", "réponse:", "answer:")

_FR_WORDS = (
    "combien", "quelle", "quelles", "quel", "quels", "résumez", "résume",
    "factures", "facture", "impayées", "impayé", "impayés", "loyer", "bail",
    "contrat", "reçus", "reçu", "montant", "payé", "payés", "avons", "êtes",
    "votre", "notre", "une",
)


def _detect_french(question: str) -> bool:
    q = question.lower()
    return sum(1 for w in _FR_WORDS if re.search(rf"\b{w}\b", q)) >= 2


def build_prompt(question: str, context: str) -> str:
    lang = "Answer in French." if _detect_french(question) else "Answer in English."
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Documents:\n{context}\n\n"
        f"Question: {question}\n"
        f"{lang}\n"
        f"Answer:"
    )


def _norm_sentence(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower().rstrip(".!?")


def clean_answer(text: str, question: str) -> str:
    cleaned = text.strip()
    for marker in ANSWER_MARKERS:
        if cleaned.lower().startswith(marker):
            cleaned = cleaned[len(marker):].strip()
    q = question.strip()
    if q and cleaned.lower().startswith(q.lower()):
        cleaned = cleaned[len(q):].strip()
    sentences = [s.strip() for s in _SENTENCE_END.split(cleaned) if s.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        key = _norm_sentence(s)
        if key and key not in seen:
            seen.add(key)
            unique.append(s)
    while len(unique) > 1 and not unique[-1].endswith((".", "!", "?")):
        unique.pop()
    if len(unique) > MAX_ANSWER_SENTENCES:
        unique = unique[:MAX_ANSWER_SENTENCES]
    return " ".join(unique)


def generate_answer(question: str, context: str, max_tokens: int = MAX_ANSWER_TOKENS) -> str:
    server = get_server()
    result = server.infer(build_prompt(question, context), max_tokens=max_tokens)
    return clean_answer(result.text, question)
