# Build Plan — Africa Deep Tech Challenge 2026

**Deadline**: Aug 24–25, 2026
**Start date**: Jul 29, 2026
**Total time**: 4 weeks
**Constraint**: fully offline, 8GB RAM laptop

> **Note on the pivot**: the project began as "Karatasi" (OCR form extraction and auto-fill of scanned forms) and pivoted mid-build to its current form — **SME Brief**, an offline RAG question-answering system over a business's own documents. The plan below reflects what actually shipped.

## Milestones

| Milestone | Window | Status |
|---|---|---|
| OCR / form-extraction pipeline (Karatasi direction) | Weeks 1–2 | ✅ Built, then replaced by the pivot |
| Pivot to offline RAG QA — generator, ingest, store, router | Week 3 | ✅ Complete |
| Gold-QA eval harness (50 questions) | Week 3 | ✅ Complete — **PASS 50/50** |
| Semantic answers (retriever + context + LLM) | Week 3 | ✅ Complete |
| Tests rewrite for the RAG stack | Week 4 | ⏳ In progress |
| Optional ask-a-question UI | Week 4 | ⏳ Optional |
| Docs/README final pass, demo, submission | Week 4 (Aug 19–25) | ⏳ In progress |

## Weeks 1–2 — OCR / Form Extraction (what shipped)

The original Karatasi direction, built and then replaced:

- [x] OpenCV image preprocessing: grayscale, adaptive thresholding, deskew, denoise, DPI normalization, web-portal detection (`src/ocr/preprocess.py`)
- [x] Typed OCR via Tesseract, region-of-interest cropping, confidence scoring (`src/ocr/typed.py`)
- [x] Handwriting OCR via TrOCR (base handwritten), lazy-loaded with explicit unload (`src/ocr/handwriting.py`)
- [x] Layout detection: contour-based region classification (label/field/checkbox/signature/photo)
- [x] Multipage PDF support (per-page render + OCR, combined text)
- [x] Form templates (KRA_PIN, DRIVING_LICENSE, ID_APPLICATION, LAND_BOARD, BIRTH_*)
- [x] Quality checks: auto-rotate, blur detection, non-form heuristics
- [x] LLM integration (Qwen2.5-1.5B via llama.cpp) for form type + field extraction
- [x] PDF export via PyMuPDF overlay (filled text, signature/photo crops)
- [x] Streamlit UI with editable fields, preview, color-coded regions, Swahili strings

**Fate**: the pivot deleted the app modules (`src/app.py`, `src/export/`, `src/forms/`, `src/pipeline.py`, `src/ui/`, `src/ocr/handwriting.py`). Only `src/ocr/preprocess.py` and `src/ocr/typed.py` survive, as legacy code outside the RAG answer path.

## The Pivot (Week 3) — Offline RAG QA

**Why**: the challenge is "The Laptop LLM Challenge". Asking questions about a company's own documents — and getting exact, cited answers offline — is a more compelling offline-AI demo than form auto-fill, and it plays to the LLM's strengths instead of fighting them (the 1.5B model was too slow and unreliable for primary field extraction).

### Delivered (Week 3)

- [x] **Synthetic corpus generator** (`data/synthetic/generator.py`): builds `manifest.json` (single source of truth: 60 docs — 34 invoices, 14 receipts, 6 contracts, 6 statements), `gold_qa.json` (50 questions with gold values + source files; 46 SQL / 4 semantic), and generated `documents/` (PDFs + scanned PNGs). Regenerates cleanly without `--force`.
- [x] **Ingest CLI** (`src/ingest/`, `venv/bin/python -m src.ingest [--db PATH] [--force]`): manifest → structured rows + chunks + embeddings; PDF text via PyMuPDF, scanned PNGs via venv-bundled Tesseract; line-preserving chunks ≤500 chars.
- [x] **Single-file storage** (`src/storage/`): SQLite `data/smebrief.db` + sqlite-vec `vec_chunks` (384-dim cosine); `FinanceStore` as the typed access layer and swappable seam (pgvector).
- [x] **Multilingual embeddings** (`src/embeddings.py`): multilingual-e5-small, 384-dim, offline-only, e5 passage/query prefixes.
- [x] **Query router** (`src/retrieval/router.py`): `QueryRouter` with 12 ordered SQL intent handlers (contract clauses, statement closing balance, by-code, paid-by-supplier, issued totals/lists, receipts by month, unpaid, receipts-over-threshold, VAT, supplier totals, total receipts) + semantic fallback.
- [x] **Semantic RAG** (`src/rag/`): retriever (lease-keyword routing + cosine kNN k=8), context builder (4000-char cap, `[file page N]` labels), LLM answer generation (Qwen2.5-1.5B, ≤3 sentences, answer cleaning).
- [x] **Gold-QA eval harness** (`eval/run_eval.py`): scores values + files per question; exit 0 only on 50/50. **Verified PASS 50/50 FAIL_IDS=[]**.
- [x] `requirements.txt` updated for the RAG stack (dropped TrOCR/faiss/reportlab; added sentence-transformers, sqlite-vec, langdetect, psutil).

## Week 4 — Remaining Work (Aug 19–25)

1. **Rewrite tests for the RAG stack** — the existing `tests/` (test_extracted_field.py, test_pdf_export.py, test_ui_features.py) import deleted Karatasi modules and fail collection. Replace with: generator consistency (manifest ↔ gold_qa ↔ documents), ingest idempotency (re-run without --force), router per-category accuracy, eval harness.
2. **Optional: ask-a-question UI** — `streamlit` is still in requirements; a minimal chat-over-corpus screen would make the demo tangible. Not required for the 50/50 eval.
3. **Final docs/README pass** — already rewritten with this pivot; verify against whatever ships in Week 4.
4. **Demo + submission** — demo video + submission before the Aug 24–25 deadline.

## How to Verify

```bash
venv/bin/python data/synthetic/generator.py   # regenerate corpus (no --force needed)
venv/bin/python -m src.ingest --force          # rebuild data/smebrief.db from manifest
venv/bin/python eval/run_eval.py               # expect PASS 50/50 FAIL_IDS=[] (exit 0)
```
