# Architecture

## Overview

SME Brief is an offline retrieval-augmented generation (RAG) system that answers business questions about a Senegalese SME's own documents — invoices, receipts, contracts, and supplier statements — in French or English. Every component runs locally: single-file SQLite storage, on-disk embeddings, and a llama.cpp LLM. No cloud calls, no daemon, no API keys.

The system is *hybrid by design*: questions about money (amounts, counts, dates, VAT) are answered with **deterministic SQL** over structured rows, never guessed by an LLM; open questions (summaries, contract clauses) fall back to **semantic RAG** — vector retrieval + LLM answer generation. Every answer carries the source file(s) it came from.

```
"Combien de factures sont impayées ?"   →   SQL intent  →   "3 factures"  (files: […])
"What was invoice AT-2024-0007?"        →   SQL intent  →   "8,120.00 USD" (files: [invoice_AT-2024-0007.pdf])
"Résumez le contrat de bail"            →   semantic    →   LLM answer over retrieved chunks
```

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  data/synthetic/generator.py                                             │
│  - manifest.json   (single source of truth: 60 docs + structured rows)   │
│  - gold_qa.json    (50 gold questions: values, files, sql_path)          │
│  - documents/      (generated PDFs + scanned PNGs, gitignored)           │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  INGEST  (venv/bin/python -m src.ingest [--db PATH] [--force])           │
│                                                                          │
│  1. upsert documents row (type/lang/date/page_count)                     │
│  2. write structured financial rows (invoices/receipts/contracts/        │
│     statements) — deterministic SQL answers                              │
│  3. extract per-page text: PDFs via PyMuPDF, scanned PNGs via            │
│     bundled Tesseract (LD_LIBRARY_PATH + TESSDATA_PREFIX pinned to venv) │
│  4. chunk text at line boundaries (MAX_CHUNK_CHARS = 500)                │
│  5. embed chunks with multilingual-e5-small (384-dim, e5 "passage: ")    │
│  6. store chunks + float32 vectors                                       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  STORE — single-file SQLite  data/smebrief.db  (no daemon, ACID)         │
│                                                                          │
│  documents, invoices, receipts, contracts, statements,                   │
│  statement_entries, chunks                                               │
│  + vec_chunks (sqlite-vec vec0: float[384] cosine)                       │
│  FinanceStore = typed access layer = the swappable seam (pgvector)       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  QUERY  — QueryRouter.answer(question) → Answer(values, files, text,     │
│                                          route 'sql' | 'semantic')       │
│                                                                          │
│  12 ordered SQL intent handlers  ────────────────┐                       │
│  (_contract_clause, _statement_closing, _by_code,│   if no intent hits   │
│   _paid_by_supplier, _issued_totals, _issued_list,▼                       │
│   _receipts_in_month, _unpaid, _receipts_over,   ┌───────────────────────┴──────┐
│   _vat_total, _supplier_total, _total_receipts)  │  SEMANTIC (src/rag/)         │
│  └── deterministic SQL answer                    │  retriever: lease-keyword     │
│       (46 of 50 gold questions)                  │   → full lease PDF, else      │
│                                                  │   kNN k=8 over vec_chunks     │
│                                                  │  build_context (4000-char cap)│
│                                                  │  LLMServer.infer (Qwen2.5-    │
│                                                  │   1.5B, ≤128 tokens, ≤3 sents)│
│                                                  │  clean_answer (markers,       │
│                                                  │   dedupe, truncate)           │
│                                                  └───────────────────────────────┘
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
                         Answer + cited files
```

## Query Routing

`QueryRouter.answer()` (src/retrieval/router.py) tries the 12 ordered intent handlers; the first that matches returns a deterministic SQL answer. If none match, the `_semantic` fallback runs the RAG path.

| # | Handler | Triggers | Returns |
|---|---|---|---|
| 1 | `_contract_clause` | rent/loyer, penalty/pénalité, payment terms, term/durée, deposit/dépôt, interest/taux, credit line | Clause value from contracts JSON (per contract file) |
| 2 | `_statement_closing` | solde / closing balance / relevé | Net of statement entries (invoice − payment) |
| 3 | `_by_code` | code pattern `[A-Z]{2,3}-\d{4}-\d{3,4}` | Invoice total or receipt amount |
| 4 | `_paid_by_supplier` | pay/paid + supplier + period | Sum of paid invoices in range |
| 5 | `_issued_totals` | total + issued/émises | Sum of invoice totals in period |
| 6 | `_issued_list` | issued/émises + period | Invoice numbers |
| 7 | `_receipts_in_month` | receipt/reçu + month | Receipt numbers + amounts |
| 8 | `_unpaid` | unpaid/impayé | Unpaid list / count / total (per currency) |
| 9 | `_receipts_over` | over / plus de + receipt | Receipts > 100 000 XOF: count/sum/list |
| 10 | `_vat_total` | tva/vat + period | VAT sum (French docs only) |
| 11 | `_supplier_total` | total + supplier | 2024 yearly spend per supplier |
| 12 | `_total_receipts` | total receipts | Sum of all receipts |
| — | `_semantic` | everything else | RAG answer (route = 'semantic') |

Formatting mirrors the gold generator so answers match gold text: XOF uses space-separated thousands (`8 120`), USD uses two decimals (`8,120.00`).

## Database Schema

Defined in `src/storage/db.py`; applied on connect (`PRAGMA foreign_keys = ON`).

| Table | Columns | Notes |
|---|---|---|
| `documents` | id, file (UNIQUE), doc_type, lang, date, page_count, ocr_pages, ingested_at | doc_type: invoice/receipt/contract/statement/other |
| `invoices` | id, doc_id→documents, number, date, supplier, buyer, currency, amount (subtotal), vat, vat_rate, total, paid (0/1), paid_date, payment_terms | |
| `receipts` | id, doc_id, number, date, amount, currency, from_name | |
| `contracts` | id, doc_id, contract_type, clauses (JSON dict) | rent, penalty, term, deposit, interest, credit line |
| `statements` | id, doc_id, supplier, period | e.g. "Q1 2024" |
| `statement_entries` | id, statement_id, date, ref, amount, kind (invoice\|payment) | closing balance = Σ invoice − Σ payment |
| `chunks` | id, doc_id, page, chunk_idx, lang, text | chunk_idx is global across pages |
| `vec_chunks` | rowid, embedding float[384] — sqlite-vec vec0, cosine | rowid = chunks.id |

All child rows reference `documents(id) ON DELETE CASCADE` — deleting a document removes its structured rows, chunks, and vectors. `delete_all()` wipes in dependency order for a clean `--force` rebuild.

## Module Map

| Module | Role | Key surface |
|---|---|---|
| `src/embeddings.py` | Multilingual embedding helpers | `embed_documents`, `embed_query`; e5 prefixes; `local_files_only`; lru_cache singleton |
| `src/ingest/ingest.py` | Corpus → store | `ingest_manifest()`, per-type loaders, `extract_pdf_text`, `extract_image_text`, `chunk_document` |
| `src/storage/db.py` | Schema + connection | `connect(db_path)` (loads sqlite-vec, applies SCHEMA), `default_db_path()` |
| `src/storage/store.py` | Typed store | `FinanceStore`: `run_sql`, `upsert_document`, `delete_*`, `set_*`, `add_chunks`, `vector_search`; `get_store()` singleton |
| `src/retrieval/router.py` | Intent routing | `QueryRouter.answer()`, `Answer` dataclass, entity extraction (suppliers, months, periods) |
| `src/rag/retriever.py` | Retrieval | lease-keyword routing to the full lease PDF, else `vector_search(k=8)` |
| `src/rag/context.py` | Context assembly | `build_context(chunks, max_chars=4000)` — `[file page N]` headers |
| `src/rag/answers.py` | LLM answer generation | `generate_answer`, `clean_answer`; ≤3 sentences, ≤128 tokens |
| `src/rag/__init__.py` | Semantic pipeline | `answer_semantic(store, q, max_chunks=8, max_chars=4000) → (files, text)` |
| `src/llm/serve.py` | LLM server | `LLMServer.infer()`, lazy load, mmap, 300s idle unload; `get_server()` |
| `eval/run_eval.py` | Gold-QA harness | scores values + files per question; exit 0 only on 50/50 |

## Design Decisions

### Single-file SQLite + sqlite-vec instead of a vector DB daemon
The knowledge base is one SQLite file: structured rows, chunk text, and float32 embeddings coexist; cosine kNN runs on the `vec_chunks` vec0 virtual table. No separate Chroma/FAISS store, no daemon to keep alive — ideal for an offline laptop demo, and the whole store is a single copyable artifact. `FinanceStore` is the seam: the same schema ports to Postgres/pgvector if scale ever demands it.

### Deterministic SQL first, LLM never for money
Money answers must be exact. 46 of 50 gold questions are answered by SQL over structured rows — an LLM can hallucinate a total, SQL cannot. The LLM is used only for the 4 open questions (summaries, clause descriptions) where determinism isn't required.

### e5 passage/query prefixing
multilingual-e5-small improves retrieval when passages are prefixed with `"passage: "` and queries with `"query: "`. The storage layer is prefix-agnostic — it stores plain vectors; only the embed callers apply prefixes.

### Offline-only model loading
Embeddings load with `local_files_only=True` and the LLM points at a local GGUF. A machine without the models/ directory fails loudly at first inference rather than silently phoning home.

### Chunking preserves line structure
Chunks split at line boundaries (≤500 chars), never mid-line. Invoice, receipt, and contract text is line-structured, so chunks stay readable and self-contained — retrieval quality depends on this.

### 4000-char context inside a 4096-token window
`build_context` accumulates `[file page N]`-labelled blocks up to a 4000-char cap, leaving the 4096-token LLM window room for the system prompt, question, and answer.

### Lease questions bypass kNN
A contract's clauses span its whole text; cosine similarity would return only the most similar chunk. Lease-keyword questions therefore route to the full warehouse-lease PDF, ordered by page.

### Answer cleaning keeps LLM output tight
`clean_answer` strips `assistant:` / `réponse:` / `answer:` markers and a repeated-question prefix, dedupes sentences, drops incomplete trailing sentences, and caps at 3 sentences — so a 1.5B model's output stays a concise, citation-ready answer.

## Evaluation Loop

`eval/run_eval.py` loads `data/synthetic/gold_qa.json` (50 questions; fields: id, category, question, lang, gold_answer, gold_values `[{currency, value}]`, gold_source, gold_files, sql_path) and runs each through `QueryRouter`. A question passes when its **values** (currency + value, rounded 3dp, sorted) and **files** (set equality) both match gold. Any failure prints `FAIL <id> [route] <question>` with got-vs-gold; the exit code is 0 **only** on 50/50.

```bash
venv/bin/python -m src.ingest --force   # rebuild the store from the manifest
venv/bin/python eval/run_eval.py        # PASS 50/50 FAIL_IDS=[] (exit 0)
```
