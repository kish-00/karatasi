# SME Brief — Devpost Submission Copy

> Africa Deep Tech Challenge 2026 — "The Laptop LLM Challenge" (AI on 8GB RAM laptops, fully offline)
> Deadline: Aug 24–25, 2026. Submit at https://adtc-2026.devpost.com/

---

## Project title

**SME Brief — Offline bilingual RAG for African SMEs**

## Tagline (one line)

**Ask your company's documents in French or English — cited answers, fully offline, on an 8GB laptop.**

## Elevator pitch (30s read)

Small businesses keep their books in invoices, receipts, contracts, and bank statements — in their local language, almost never in a tidy database. Cloud AI assistants can't help in a region where connectivity is unreliable. SME Brief is a retrieval-augmented question-answering system that runs **100% offline on an ordinary 8GB laptop**: ask "Combien de factures sont impayées ?" and get an exact, cited answer in seconds. Money questions are answered by **deterministic SQL** over structured rows (never LLM-guessed); open questions use **semantic RAG** over a single-file vector store with a small local LLM. Everything — documents, vectors, answers — lives in one SQLite file, with zero cloud calls, zero API keys, zero daemons. A gold suite of 50 bilingual question/answer pairs scores **50/50**, and the whole system fits in **~1.5–2GB RAM**.

## What it does (2–3 paragraphs)

SME Brief answers business questions about a company's own documents — invoices, receipts, contracts, supplier statements — in **French or English**, with **cited sources** on every answer. It is hybrid by design: questions about money (amounts, counts, dates, VAT) are answered by deterministic SQL over structured rows, so a total can never be hallucinated; open questions (summaries, contract clauses) fall back to semantic RAG — vector retrieval over the document store feeding a small local LLM (Qwen2.5-1.5B) that generates a concise, sourced answer.

The system runs entirely offline on an 8GB RAM laptop: multilingual embeddings (multilingual-e5-small), a single-file SQLite + sqlite-vec knowledge base, and a CPU-only llama.cpp LLM. No daemon, no cloud calls, no API keys — the whole knowledge base is one copyable SQLite file. A Streamlit chat UI provides a bilingual experience with suggested questions and per-answer route + source display, and a gold evaluation suite of 50 question/answer pairs verifies every change (currently **PASS 50/50**).

## How we built it

| Layer | Technology | Why |
|---|---|---|
| Embeddings | multilingual-e5-small | 384-dim, French + English, offline |
| Knowledge base | SQLite + sqlite-vec | single file, no daemon, ACID, cosine kNN |
| LLM | Qwen2.5-1.5B-Instruct Q4_K_M via llama.cpp | ~1GB, CPU-only, bilingual instruction-following |
| Structured data | SQLite (invoices/receipts/contracts/statements) | deterministic, exact money answers |
| PDF/scan text | PyMuPDF + venv-bundled Tesseract | offline extraction, zero system install |
| UI | Streamlit | bilingual chat with cited sources + route badges |
| Eval | 50-question gold suite (46 SQL + 4 semantic) | objective quality gate, exit 0 only at 50/50 |

## Challenges we ran into

- **The pivot**: the project started as OCR form extraction ("Karatasi") — the 1.5B model was too slow and unreliable for primary field extraction. We pivoted to RAG question-answering, which plays to the LLM's strengths: exactness for money is delegated to deterministic SQL, and the LLM only writes open-ended answers. (Full rationale in `docs/BUILD_PLAN.md`.)
- **Offline-first discipline**: every component had to work without internet — `local_files_only=True`, a venv-bundled Tesseract, models pre-downloaded.
- **Thread-safety in Streamlit**: `get_store()` is a process-wide singleton; each AppTest/UI thread needed `check_same_thread=False` on the SQLite connection, with all store access serialized by a lock.
- **Date bugs caught by tests**: an invalid `2024-06-31` period endpoint (June has 30 days) — caught and fixed while writing the router test suite.

## Accomplishments we're proud of

- **50/50 on a gold bilingual eval suite** — every answer verified against exact values and source files
- **Deterministic money answers** — SQL for anything numeric; the LLM never touches a total
- **~1.5–2GB total footprint** on an ordinary laptop, fully offline, no daemon
- **One SQLite file = the whole knowledge base** — copyable, backup-able, demo-reliable

## What we learned

- Match the model to the job: a 1.5B CPU model is great for short grounded answers, not for high-precision extraction — split the problem accordingly (SQL for facts, RAG for language).
- Offline-first forces simple, robust architecture — and simplicity made the demo more reliable.
- A gold eval suite turns "it seems right" into a measurable 50/50 gate.

## Built with

Python 3.11 · Streamlit · SQLite · sqlite-vec · sentence-transformers (multilingual-e5-small) · llama.cpp / llama-cpp-python · Qwen2.5-1.5B-Instruct · PyMuPDF · Tesseract · pytest

## Optional: what's next

- Multi-company workspaces (per-SME knowledge bases)
- pgvector backend for corpus scale beyond 100k chunks
- More languages (Wolof, Swahili, Hausa…)
- PDF ingestion of the user's *own* documents at runtime

---

## Devpost fields cheat-sheet

- **Gallery images** (required): use `docs/demo/ui_landing.png`, `ui_answer_sql_fr.png`, `ui_answer_sql_en.png`, `ui_answer_semantic.png` (screenshots already captured).
- **Demo video**: follow `docs/demo/DEMO_SCRIPT.md` (90–120s), upload to YouTube/Devpost.
- **URL**: GitHub repo (push `main` — currently 4 commits ahead of origin).
- **Team**: add teammates in Devpost before submitting.
