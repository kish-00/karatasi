from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROUTE_LABELS = {"sql": "SQL", "semantic": "Semantic (RAG)"}

SUGGESTED_QUESTIONS = [
    ("Combien de factures sont impayées ?", "fr"),
    ("What was invoice AT-2024-0007?", "en"),
    ("Quel est le loyer mensuel de l'entrepôt ?", "fr"),
    ("What did we pay AfricaTextiles Ltd between January and March 2024?", "en"),
    ("What is the total amount of all unpaid invoices?", "en"),
    ("Combien avons-nous payé à SENEXPORT en 2024 ?", "fr"),
    ("Quelles sont les conditions de paiement du bail de l'entrepôt ?", "fr"),
    ("What is the closing balance on the AfricaTextiles Q1 2024 statement?", "en"),
    ("Montrez-moi les reçus de plus de 100 000 FCFA.", "fr"),
    ("What is our total VAT paid in Q1 2024?", "en"),
]

SUGGESTED_CHIPS = [q for q, _ in SUGGESTED_QUESTIONS]


def fmt_value(value: dict) -> str:
    currency = value.get("currency", "count")
    amount = value.get("value", 0.0)
    if currency in ("count", "pct", "days", "months"):
        return f"{amount:g} {currency}"
    if currency == "XOF":
        return f"{int(round(amount)):,} FCFA".replace(",", " ")
    return f"{amount:,.2f} {currency}"


def format_answer(turn: dict) -> list[str]:
    lines = [turn["text"]] if turn.get("text") else []
    if turn.get("values"):
        rendered = " | ".join(fmt_value(v) for v in turn["values"])
        lines.append(f"**Values:** {rendered}")
    if turn.get("files"):
        files = ", ".join(turn["files"])
        lines.append(f"**Sources:** {files}")
    return lines


def run_query(question: str) -> None:
    from src.retrieval.router import QueryRouter
    from src.storage.store import get_store

    router = QueryRouter(get_store())
    try:
        with st.spinner("Answering…"):
            ans = router.answer(question)
    except Exception as exc:
        st.session_state.history.append(
            {"question": question, "error": f"Error: {exc}"}
        )
        return
    st.session_state.history.append(
        {
            "question": question,
            "text": ans.text,
            "values": ans.values,
            "files": ans.files,
            "route": ROUTE_LABELS.get(ans.route, ans.route),
        }
    )


def main() -> None:
    st.set_page_config(page_title="SME Brief", page_icon="📄", layout="centered")
    st.title("SME Brief")
    st.caption(
        "Offline RAG over Aya Traoré's SME documents — French & English, with cited sources."
    )

    if "history" not in st.session_state:
        st.session_state.history = []

    with st.expander("Try a demo question", expanded=not st.session_state.history):
        for suggestion in SUGGESTED_CHIPS:
            if st.button(suggestion, key=f"sugg_{suggestion}", use_container_width=True):
                run_query(suggestion)

    with st.form("question_form", clear_on_submit=True):
        question = st.text_input(
            "Ask about invoices, receipts, contracts, or bank statements",
            placeholder="e.g. Combien de factures sont impayées ?",
        )
        submitted = st.form_submit_button("Ask", use_container_width=True)

    if submitted and question.strip():
        run_query(question.strip())

    for turn in reversed(st.session_state.history):
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            if "error" in turn:
                st.error(turn["error"])
            else:
                for line in format_answer(turn):
                    st.markdown(line)
                st.caption(f"route: {turn['route']}")

    if st.session_state.history:
        st.button("Clear conversation", on_click=lambda: st.session_state.history.clear())


if __name__ == "__main__":
    main()
