# SME Brief — Continuation Prompt (new session)

Paste this block into a fresh session to pick up exactly where the last one left off.

---

You are continuing work on **SME Brief — Offline Local RAG for African SMEs** at
`/home/kish/Documents/projects/smebrief` (Africa Deep Tech Challenge 2026, deadline Aug 24–25 2026;
constraint: runs offline on an 8GB laptop). The repo is a RAG question-answering system over a
synthetic Senegalese SME financial corpus (invoices, receipts, contracts, statements; French + English).
The pivot from the original "Karatasi" OCR form-extraction app is committed and the docs (README.md,
docs/ARCHITECTURE.md, docs/TECH_STACK.md, docs/BUILD_PLAN.md) are CURRENT — trust them.

## Environment quirks (critical)

1. Tool output in this environment is corrupted (frames duplicated/merged). **Workaround: write
   results to files and read ONE verdict line at a time. Trust only single-line outputs** (e.g. write
   `PASS 50/50 FAIL_IDS=[]` to a file, then read it). Do not chase apparent contradictions from
   multi-line read output.
2. A hook flags newly added comments/docstrings → keep code self-documenting (named conditions,
   well-named variables). Avoid `#` comments and docstrings in new/edited code.
3. Run everything via the repo venv: `venv/bin/python …` (Tesseract is bundled at `venv/bin/tesseract`).
4. The `task()` delegation categories in this environment are BROKEN (invalid model config) — write
   docs/code directly rather than delegating to writing/general agents.

## Verified current state (do NOT re-verify; trust)

- **Gold-QA eval: PASS 50/50, FAIL_IDS=[]** — `venv/bin/python eval/run_eval.py` exits 0.
- Router: 12 intent handlers → deterministic SQL for 46 questions; semantic RAG fallback (src/rag/)
  for the 4 lease/summarize questions. Diagnostics clean.
- Semantic path is BUILT and wired: `src/rag/retriever.py` (lease-keyword route + kNN k=8),
  `src/rag/context.py` (4000-char cap), `src/rag/answers.py` (Qwen2.5-1.5B, ≤3 sentences,
  `clean_answer` markers/dedupe), `answer_semantic()` in `src/rag/__init__.py`, called by
  `QueryRouter._semantic`.
- Data consistency: manifest has 60 docs (34 invoices, 14 receipts, 6 contracts, 6 statements —
  all unique files); DB = 60 documents / 82 chunks; `data/synthetic/generator.py` regenerates
  manifest + gold_qa cleanly WITHOUT `--force`.
- Ingest aborts if DB populated and `--force` not passed; DB rebuilt clean with `--force`.
- Docs are current (rewritten + committed in the pivot commit): README.md, docs/ARCHITECTURE.md,
  docs/TECH_STACK.md, docs/BUILD_PLAN.md. `scripts/download_models.py` downloads the Qwen GGUF +
  multilingual-e5-small (TrOCR/all-MiniLM removed).

## Architecture (current, accurate)

- `data/synthetic/generator.py` (891 lines) — synthetic corpus generator: `manifest.json` (single
  source of truth), `gold_qa.json` (50 questions: ids like `num_01`, `tmp_07`, `con_08`, `mul_05`;
  fields `question`, `lang`, `gold_answer`, `gold_values` [{currency,value}], `gold_files`,
  `sql_path` 'sql'|'semantic'), and `data/synthetic/documents/` (PDFs + scanned PNGs, gitignored).
  Mixes `facture_`/`invoice_` prefixes by language; scanned docs are `.png`.
- `src/storage/db.py` (123 lines) — SQLite schema: `documents`, `invoices`, `receipts`, `contracts`,
  `statements`, `statement_entries`, `chunks` + sqlite-vec `vec_chunks` (384-dim cosine).
- `src/storage/store.py` (306 lines) — `FinanceStore` (the swappable seam; ports to pgvector):
  `run_sql`, `upsert_document`, `delete_document/delete_all`, `list_documents`, `count_documents`,
  `max_doc_date`, `set_invoice/set_receipt/set_contract/set_statement`, `add_chunks`,
  `vector_search`, `get_store()`.
- `src/embeddings.py` (48 lines) — multilingual-e5-small, 384-dim, offline (local_files_only),
  e5 prefixes ("passage: "/"query: "), `embed_documents`/`embed_query`, lru_cache singleton.
- `src/ingest/ingest.py` (241 lines) — CLI `venv/bin/python -m src.ingest [--db PATH] [--force]`;
  reads manifest.json, upserts documents, sets structured rows, extracts PDF text via PyMuPDF,
  OCRs scanned PNGs via bundled Tesseract (needs `LD_LIBRARY_PATH` pointing at venv lib), chunks
  (MAX_CHUNK_CHARS=500), embeds, stores.
- `src/retrieval/router.py` (496 lines) — `QueryRouter.answer(question) -> Answer` (dataclass:
  values, files, text, route 'sql'|'semantic'). Handler order: `_contract_clause`,
  `_statement_closing`, `_by_code`, `_paid_by_supplier`, `_issued_totals`, `_issued_list`,
  `_receipts_in_month`, `_unpaid`, `_receipts_over`, `_vat_total`, `_supplier_total`,
  `_total_receipts`, then `_semantic` fallback.
- `src/rag/` — semantic path: `retriever.py` (lease markers → full `contrat_bail_entrepot.pdf`,
  else `vector_search(k=8)`), `context.py` (`build_context`, 4000-char cap), `answers.py`
  (SYSTEM_PROMPT, MAX_ANSWER_TOKENS=128, MAX_ANSWER_SENTENCES=3, `clean_answer`),
  `__init__.py::answer_semantic`.
- `src/llm/serve.py` (219 lines) — `LLMServer` (qwen2.5-1.5b-instruct-q4_k_m.gguf, context 4096,
  lazy load + mmap + 300s idle unload, temp 0.1), `infer()`, `get_server()`.
- `eval/run_eval.py` (85 lines) — harness: scores values (normalized currency+rounded 3dp) and
  files per question; `--json`, `--fail-fast`; exit 0 only on 50/50.

## Known gaps / next steps (in priority order)

1. **tests/ are broken** (pre-existing, unrelated to router work): all 3 test modules
   (`test_extracted_field.py`, `test_pdf_export.py`, `test_ui_features.py`) import deleted
   Karatasi modules and fail collection. Rewrite for the RAG stack: generator consistency,
   ingest idempotency, router per-category accuracy, eval harness.
2. **Optional: Streamlit ask-a-question UI** (streamlit still in requirements) for a tangible
   demo — chat-over-corpus screen using `QueryRouter.answer()`.
3. **Legacy cleanup (optional)**: `chromadb` and `streamlit` are unused in requirements.txt;
   `src/ocr/preprocess.py` + `typed.py` are legacy (not in the RAG path). Leave unless trimming.
4. **Demo + submission** — demo video + submission before Aug 24–25 2026.

## Commands

```bash
cd /home/kish/Documents/projects/smebrief
venv/bin/python data/synthetic/generator.py  # regenerate manifest + gold (no --force needed)
venv/bin/python -m src.ingest --force         # rebuild DB from manifest
venv/bin/python eval/run_eval.py              # expect: PASS 50/50 FAIL_IDS=[] (exit 0)
venv/bin/python -c "from src.storage.store import get_store; from src.retrieval.router import QueryRouter; a=QueryRouter(get_store()).answer('Combien de factures sont impayées ?'); print(a.text, a.files, a.route)"
```

## Reporting

When done, report: what you changed, eval result (must stay 50/50 unless you deliberately extended
the gold set), diagnostics status, and any remaining gaps. Do not re-litigate completed router fixes.
