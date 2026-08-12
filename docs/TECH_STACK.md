# Technology Stack — Decisions & Rationale

Every choice in SME Brief is driven by two constraints: **must run fully offline** and **must fit on an 8GB RAM laptop** (CPU-only inference). The domain adds a third: the corpus and questions are **bilingual (French + English)**. This document explains why each technology was chosen and what the alternatives were.

---

## Embeddings

**Chosen**: multilingual-e5-small (SentenceTransformer)
**Alternatives**: all-MiniLM-L6-v2, BGE-m3, multilingual-e5-large, cloud embedding APIs

multilingual-e5-small produces 384-dimensional vectors and covers 100+ languages — including both French and English, the two languages of the corpus and of user questions. Multilingual capability is the whole point: a query in French must retrieve chunks written in either language, so an English-only model is disqualified from the start.

e5 models recommend prefixing inputs — passages with `"passage: "`, queries with `"query: "` — which measurably improves retrieval quality and is implemented in `src/embeddings.py`. The storage layer is prefix-agnostic: it stores plain float vectors, so the prefix policy can change without a schema change.

| Option | Offline | FR+EN | RAM | Verdict |
|---|---|---|---|---|
| multilingual-e5-small | ✅ | ✅ | ~0.3GB | **Chosen** — right size, right languages |
| all-MiniLM-L6-v2 | ✅ | ❌ English-only | ~0.1GB | Used pre-pivot; cannot answer FR queries |
| multilingual-e5-large | ✅ | ✅ | ~1.5GB | Better quality, but 5× the RAM for marginal gains at this corpus size |
| BGE-m3 | ✅ | ✅ | ~2GB+ | Heavy; overkill for an 8GB laptop |
| OpenAI text-embedding-3 | ❌ cloud | ✅ | — | Violates the offline constraint |

The model is loaded with `local_files_only=True` and cached in a process-wide singleton (`lru_cache`), so the ingest pipeline and the query router never double-load it.

---

## Vector Storage

**Chosen**: SQLite + sqlite-vec
**Alternatives**: ChromaDB, FAISS, Postgres/pgvector

The knowledge base is **one SQLite file** (`data/smebrief.db`): structured financial rows, chunk text, and float32 embeddings coexist, with cosine kNN provided by the `vec_chunks` `vec0` virtual table. This is a deliberate "no daemon" design — nothing to keep alive, nothing to configure, single ACID file that can be copied, backed up, or shipped with the demo.

| Option | Offline | Deamon | ACID | Scale note | Verdict |
|---|---|---|---|---|---|
| SQLite + sqlite-vec | ✅ | none | ✅ | fine to 100k+ chunks | **Chosen** |
| ChromaDB | ✅ | separate store | partial | fine | Original choice; dropped in Week 4 legacy cleanup — heavier, no benefit at this scale |
| FAISS | ✅ | none | ❌ (in-memory) | excellent | Dropped in the pivot; needs manual persistence plumbing |
| Postgres/pgvector | ❌ server | yes | ✅ | excellent | Production-grade, but a server is the wrong shape for an offline laptop |

The `FinanceStore` class is the swappable seam: the same schema and method surface ports to Postgres/pgvector if the corpus ever outgrows SQLite. At the current corpus (60 documents, ~82 chunks) and even at 100k+ chunks, SQLite is more than sufficient.

---

## LLM

**Chosen**: Qwen2.5-1.5B-Instruct Q4_K_M (GGUF) via llama-cpp-python
**Alternatives**: Phi-3-mini, Llama-3.2-1B, larger GGUF quants, cloud APIs

The LLM answers only the *semantic* questions (summaries, clause descriptions — 4 of 50 gold questions); money questions are deterministic SQL and never touch the model. So the requirement is: good enough French/English instruction-following inside an 8GB budget, not frontier quality.

`LLMServer` (`src/llm/serve.py`) loads the Q4_K_M GGUF CPU-only (`n_gpu_layers=0`) with a 4096-token context (RAG context + answer), temperature 0.1 for deterministic output, lazy-load on first inference, memory-mapping, and a 300-second idle unload that frees the ~1GB when unused.

| Option | RAM | Offline | FR | Verdict |
|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct Q4_K_M | ~1GB | ✅ | ✅ | **Chosen** — best quality-per-GB for the budget |
| Phi-3-mini (3.8B) | ~2.5GB | ✅ | weak | Too heavy with embeddings loaded, weaker French |
| Llama-3.2-1B | ~0.9GB | ✅ | weak | Comparable size, noticeably worse French/instruction following |
| Cloud LLM APIs | — | ❌ | ✅ | Violates the offline constraint |

---

## Text Extraction

**Chosen**: PyMuPDF (fitz) for PDFs, Tesseract (via pytesseract) for scanned PNGs
**Alternatives**: pdfplumber/pdfminer, EasyOCR, PaddleOCR

Ingest needs per-page text for two document shapes: generated PDFs (a clean text layer) and scanned PNGs (pixel images).

- **PyMuPDF** reads the PDF text layer directly — fast, precise page splits, no OCR needed for the majority of the corpus.
- **Tesseract** handles the scanned PNGs. The binary is **bundled inside the repo venv** (`venv/bin/tesseract`), so there is no system-install prerequisite; `extract_image_text` pins `LD_LIBRARY_PATH` and `TESSDATA_PREFIX` to the venv so the bundled binary resolves its libraries and `eng.traineddata`. Heavier alternatives (EasyOCR/PaddleOCR) are GPU-oriented and overkill for clean generated scans.

| Option | Speed | Offline | Notes | Verdict |
|---|---|---|---|---|
| PyMuPDF | instant | ✅ | direct text layer | **Chosen** for PDFs |
| Tesseract (bundled) | fast | ✅ | no system install | **Chosen** for scans |
| pdfplumber/pdfminer | slower | ✅ | more deps, same result | Not needed |
| EasyOCR/PaddleOCR | slow on CPU | ✅ | GPU-oriented, heavy | Overkill |

---

## Storage Engine

SQLite, single file, ACID (`PRAGMA foreign_keys = ON`, `ON DELETE CASCADE`). The alternative is a client-server database, which fails the "ordinary laptop, zero setup, demo-reliable" test. `db.py` owns the schema; `store.py` owns the typed access layer; the ingest pipeline, query router, and eval harness all build against `FinanceStore` — one seam to swap if the target becomes server-scale.

---

## Summary

| Layer | Chosen | Why |
|---|---|---|
| Embeddings | multilingual-e5-small | 384-dim, FR+EN, offline |
| Vector store | SQLite + sqlite-vec | one file, no daemon, ACID |
| LLM | Qwen2.5-1.5B Q4_K_M (llama.cpp) | ~1GB, CPU-only, bilingual |
| PDF text | PyMuPDF | fast text-layer extraction |
| Scanned OCR | Tesseract (venv-bundled) | offline, zero system install |

## Dropped in the Pivot

The project originally shipped as "Karatasi" (OCR form extraction) and pivoted to RAG QA. Dropped with it: **TrOCR** (handwriting — no handwriting in the new domain), **reportlab** (PDF overlay export), **FAISS** (replaced by sqlite-vec), **torchvision/transformers/sentencepiece** (TrOCR stack), and **chromadb** (never used after the pivot — the vector store is sqlite-vec; removed from `requirements.txt`). The Karatasi-era OCR code lives in `archive/ocr/` (preprocess.py, typed.py) for reference and is not part of the RAG answer path. Actual resident memory today: ~1.5–2GB (LLM ~1GB + embeddings model), well inside the 8GB budget.
