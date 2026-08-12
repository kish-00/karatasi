# SME Brief — Devpost Submission (copy/paste blocks)

Copy each numbered block into the matching Devpost field. Sections 1–13 are final.
All sections final. Section 14 numbers are from the completed profiler run (see submission.json in the submission repo).

---

## 1. Project title
SME Brief — Offline bilingual RAG for African SMEs

## 2. Tagline (one line)
Ask your company's documents in French or English — cited answers, sovereign-by-default, on an 8GB laptop.

## 3. Elevator pitch
SME Brief is an offline, local-first RAG assistant that lets a non-technical African SME owner ask plain-language questions about their own business documents — supplier invoices, contracts, statements — in French or English, and get a short, citation-grounded answer in the same language. No cloud. No per-seat SaaS. No data leaving the laptop. It runs on the same 8GB machine the business already owns — which matters because most African SMEs cannot rely on stable connectivity or afford recurring SaaS fees.

## 4. What it does
SME Brief retrieves answers from the business's own documents. A hybrid SQL + RAG pipeline answers 46 of 50 gold questions deterministically from structured financial data (invoices, payments, balances) — the LLM never touches the money. Only open-domain questions (summaries, contract clauses) fall back to semantic RAG: vector retrieval over a local document store feeding a 1.5B instruct model prompted to answer only from retrieved context. Every answer carries a citation back to the source document. Runs fully offline on an 8GB RAM laptop.

## 5. African Use Case Relevance
- Sovereign by design — documents never leave the laptop; verifiably zero outbound calls at runtime.
- Language reality — West-African commerce is bilingual (FR/EN); answers in the question's language, normalizing FR/EN supplier/invoice terminology.
- Currency reality — formats and reasons across XOF, USD, EUR, GBP with locale-correct rendering.
- Cost reality — no per-seat SaaS, no GPU, no cloud bill; only the 8GB laptop already on the desk.
- Verifiability — citations let an owner or auditor trust every figure.
- Federated-by-default — scales to many SMEs without centralizing their documents.

## 6. How we built it (tech stack)
- Embeddings: multilingual-e5-small (384-dim, FR+EN, offline)
- Knowledge base: SQLite + sqlite-vec (single file, cosine kNN)
- LLM: Qwen2.5-1.5B-Instruct Q4_K_M via llama.cpp (CPU-only, ~1GB, bilingual)
- Structured data: SQLite (invoices/receipts/contracts/statements) — deterministic money answers
- PDF/scan text: PyMuPDF + venv-bundled Tesseract (offline)
- UI: Streamlit (bilingual chat with cited sources + route badges)
- Eval: 50-question gold suite (46 SQL + 4 semantic), exit 0 only at 50/50

## 7. Challenges we ran into
- The pivot: started as OCR form extraction ("Karatasi"); the 1.5B model was too slow/unreliable for primary field extraction, so we pivoted to RAG QA — exact money delegated to deterministic SQL, LLM only writes open-ended answers.
- Offline-first discipline: local_files_only=True, venv-bundled Tesseract, pre-downloaded models; zero outbound calls at runtime.
- Thread-safety in Streamlit: process-wide singleton store with check_same_thread=False + lock.
- Date bugs caught by tests (e.g., invalid 2024-06-31) while writing the router suite.

## 8. Accomplishments we're proud of
- 50/50 on a gold bilingual eval suite
- Deterministic money answers (SQL for anything numeric)
- Federated-by-default: zero outbound network calls, verifiable by offline test
- ~1.5–2GB total footprint, fully offline, no daemon
- One SQLite file = the whole knowledge base (copyable, backup-able)

## 9. What we learned
- Match the model to the job: a 1.5B CPU model is great for short grounded answers, not high-precision extraction — split the problem accordingly.
- Offline-first forces simple, robust architecture — and simplicity made the demo more reliable.
- A gold eval suite turns "it seems right" into a measurable 50/50 gate.

## 10. Built with
Python 3.11 · Streamlit · SQLite · sqlite-vec · sentence-transformers (multilingual-e5-small) · llama.cpp / llama-cpp-python · Qwen2.5-1.5B-Instruct · PyMuPDF · Tesseract · pytest

## 11. Demo video
[YouTube/Devpost link — record using docs/demo/DEMO_SCRIPT.md (90–120s). Keep a system-monitor overlay showing RAM ~1.5–2GB and 0% network.]

## 12. Gallery images (required — upload from docs/demo/)
- ui_landing.png
- ui_answer_sql_fr.png
- ui_answer_sql_en.png
- ui_answer_semantic.png

## 13. Submission URL
https://github.com/kish-00/adtc-2026-submission

## 14. Benchmark numbers (from submission.json — profiler run complete)

Measured on: Intel i5-6200U, 7.6 GB RAM, no discrete GPU (CPU-only), Ubuntu 24.04.4 LTS

| Metric | Value |
|---|---|
| Generation speed | 8.15 tokens/sec |
| RAM at peak | 1821.75 MB |
| Time to first token | 20942.68 ms |
| Thermal throttling | Yes (92.0 °C peak core temp) |
| Accuracy (arc_easy, 50 samples) | 74.0% (acc_norm) |

### Score estimate (formula from ADTC rules)
- S_perf = 100 × (TPS / 15.0) = 100 × (8.15 / 15.0) = 54.33
- S_eff  = 100 × ((7000 − 1821.75) / 7000) = 73.98
- S_acc  = 0.74 × 100 = 74.00
- Thermal penalty = −10 (throttling observed: 92.0 °C peak)
- African-use-case bonus = +10 (african_alpha_claim: true)

S_total ≈ 0.50·74.00 + 0.30·54.33 + 0.20·73.98 − 10 + 10 = 68.10 / 110

(Note: official score is computed by ADTC organizers from submission.json; this is a self-computed estimate. The thermal penalty and African bonus cancel on the participant's i5-6200U laptop. The audit run on the organizers' better-cooled Standard Laptop is expected to remove the throttle while keeping the +10 bonus — projected audit score ≈ 78.)

## 15. Team
Ian Kinuthia (solo) — iankinuthia00@gmail.com — github.com/kish-00
