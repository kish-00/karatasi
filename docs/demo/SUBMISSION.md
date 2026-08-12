# SME Brief — Devpost Submission Copy

> Africa Deep Tech Challenge 2026 — "The Laptop LLM Challenge" (AI on 8GB RAM laptops, fully offline)
> Deadline: Aug 24–25, 2026. Submit at https://adtc-2026.devpost.com/

---

## Project title

**SME Brief — Offline bilingual RAG for African SMEs**

## Tagline (one line)

**Ask your company's documents in French or English — cited answers, federated-by-default, on an 8GB laptop.**

## Elevator pitch (30s read)

SME Brief is an offline, local-first RAG assistant that lets a non-technical African SME owner ask plain-language questions about their own business documents — supplier invoices, contracts, statements — in French or English, and get a short, citation-grounded answer in the same language. No cloud. No per-seat SaaS. No data leaving the laptop. It runs on the same 8GB machine the business already owns, which matters because most African SMEs cannot rely on stable connectivity or afford recurring SaaS fees.

## What it does (2–3 paragraphs)

SME Brief retrieves answers from the business's own documents. A hybrid SQL + RAG pipeline answers 46 of 50 gold questions deterministically from structured financial data (invoices, payments, balances) — the LLM never touches the money. Only open-domain questions (summaries, contract clauses) fall back to semantic RAG — vector retrieval over the document store feeding a 1.5B instruct model that is prompted to answer only from retrieved context. Every answer carries a citation back to the source document, so the owner can verify.

The system runs entirely offline on an 8GB RAM laptop: multilingual embeddings (multilingual-e5-small), a single-file SQLite + sqlite-vec knowledge base, and a CPU-only llama.cpp LLM. No daemon, no cloud calls, no API keys — the whole knowledge base is one copyable SQLite file. A Streamlit chat UI provides a bilingual experience with suggested questions and per-answer route + source display, and a gold evaluation suite of 50 question/answer pairs verifies every change (currently **PASS 50/50**).

## African Use Case Relevance

- **Sovereign by design.** Documents never leave the laptop. For businesses in regions with intermittent connectivity or data-residency sensitivity, "local-first" is not a feature — it is the requirement. The system is verifiably offline (zero outbound calls at runtime).
- **Language reality.** West-African commerce is bilingual (French/English) and document-heavy. SME Brief answers in the question's language and normalizes French/English supplier and invoice terminology.
- **Currency reality.** It formats and reasons across XOF, USD, EUR, and GBP — the currencies a real import/export SME actually handles — with locale-correct rendering.
- **Cost reality.** No per-seat SaaS, no GPU, no cloud bill. The only hardware is the 8GB laptop already on the desk.
- **Verifiability.** Citations let an owner or auditor trust every figure — critical where informal record-keeping is the norm.
- **Federated-by-default.** The same architecture scales to many SMEs without centralizing their documents: each runs its own instance; only aggregated, document-free insights would ever be shared (see What's next).

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
- **Offline-first discipline**: every component had to work without internet — `local_files_only=True`, a venv-bundled Tesseract, models pre-downloaded. Keeping the system *federated-by-default* — the agent never calls external services, so a disconnected laptop still answers.
- **Thread-safety in Streamlit**: `get_store()` is a process-wide singleton; each AppTest/UI thread needed `check_same_thread=False` on the SQLite connection, with all store access serialized by a lock.
- **Date bugs caught by tests**: an invalid `2024-06-31` period endpoint (June has 30 days) — caught and fixed while writing the router test suite.

## Accomplishments we're proud of

- **50/50 on a gold bilingual eval suite** — every answer verified against exact values and source files
- **Deterministic money answers** — SQL for anything numeric; the LLM never touches a total
- **A federated-by-default architecture**: zero outbound network calls at runtime, verifiable by the offline network test
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
- **Federated multi-SME analytics** — shared insights without sharing documents
- **LoRA fine-tuning** on West-African SME corpora once UDEK GPU credits land

---

## Devpost fields cheat-sheet

- **Gallery images** (required): use `docs/demo/ui_landing.png`, `ui_answer_sql_fr.png`, `ui_answer_sql_en.png`, `ui_answer_semantic.png` (screenshots already captured).
- **Demo video**: follow `docs/demo/DEMO_SCRIPT.md` (90–120s), upload to YouTube/Devpost.
- **URL**: submission repo `https://github.com/kish-00/adtc-2026-submission` *(public)*.
- **Team**: add teammates in Devpost before submitting.
