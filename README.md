# SME Brief — Offline Local RAG for African SMEs

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Offline](https://img.shields.io/badge/Runs-Offline%20%7C%208GB%20Laptop-success)](https://adtc-2026.devpost.com/)

**SME Brief** is an offline retrieval-augmented generation (RAG) system that answers business questions about a small company's own documents — in French or English — with cited sources. Built for the **Africa Deep Tech Challenge 2026** ("The Laptop LLM Challenge" — AI that runs on 8GB RAM laptops, fully offline).

```
"Combien de factures sont impayées ?"      "What was invoice AT-2024-0007?"
        │                                          │
        ▼                                          ▼
   ┌─────────────────────────────────────────────────────┐
   │  QueryRouter → SQL intents  OR  semantic RAG (LLM)  │
   │  over a single-file SQLite store (documents + vec)  │
   └─────────────────────────────────────────────────────┘
        │                                          │
        ▼                                          ▼
   "3 factures"                            "8,120.00 USD"
   files: [facture_…, …]                   files: [invoice_AT-2024-0007.pdf]
```

---

## Why SME Brief?

Small businesses keep their books in invoices, receipts, contracts, and bank statements — almost always in their local language(s), almost never in a tidy database. Answering "how much did we pay Groupe Comptoir last quarter?" means hunting through a pile of PDFs and scans. Cloud AI assistants can't help: most SMEs in West Africa work from cybercafés and local offices with unreliable connectivity.

SME Brief runs entirely offline on an ordinary 8GB laptop:

- **Bilingual** — ask in French or English, get an answer in the same language
- **Hybrid answering** — money questions are answered by *deterministic SQL* over structured rows (never LLM-guessed), open questions by semantic RAG
- **Cited answers** — every answer names the source document(s) and page
- **Gold eval suite** — 50 question/answer pairs score the router (currently 50/50)
- **Fully offline** — models load with `local_files_only=True`; one SQLite file holds the whole knowledge base; no daemon, no cloud, no API keys

**Memory footprint**: ~1.5–2GB (Qwen2.5-1.5B ~1GB + multilingual-e5-small) — comfortably inside the 8GB budget.

## Project Status

**Active development** — Africa Deep Tech Challenge 2026 (deadline: Aug 24–25, 2026).

| Milestone | Window | Status |
|---|---|---|
| OCR/extraction pipeline (original "Karatasi" direction) | Weeks 1–2 | ✅ Built, then replaced by the pivot |
| Pivot to offline RAG QA — generator, ingest, store, router | Week 3 | ✅ Complete |
| Gold-QA eval harness — 50/50 passing | Week 3 | ✅ Complete |
| Semantic answers (retriever + context + LLM) wired in | Week 3 | ✅ Complete |
| Tests rewrite for the RAG stack (36 tests green) | Week 4 | ✅ Complete |
| Ask-a-question UI (Streamlit chat) | Week 4 | ✅ Complete |
| Polish, demo, submission | Week 4 (Aug 19 – 25) | ⏳ In progress |

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Embeddings | multilingual-e5-small (SentenceTransformer) | 384-dim bilingual (FR/EN) passage & query vectors |
| Vector store | SQLite + sqlite-vec | Single-file cosine kNN (`vec_chunks` virtual table) |
| Structured store | SQLite | Deterministic SQL over invoices, receipts, contracts, statements |
| LLM | Qwen2.5-1.5B-Instruct Q4_K_M (llama.cpp) | Semantic answer generation, CPU-only, ~1GB |
| PDF text | PyMuPDF | Per-page text extraction at ingest |
| Scanned OCR | Tesseract (bundled in venv) | Text extraction for scanned PNG documents |

## Quick Start

```bash
# Prerequisites: Python 3.11

cd smebrief

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download models (Qwen2.5-1.5B GGUF + multilingual-e5-small)
python scripts/download_models.py

# 1) Regenerate the synthetic corpus (manifest + gold QA + documents)
venv/bin/python data/synthetic/generator.py

# 2) Build the knowledge base (data/smebrief.db)
venv/bin/python -m src.ingest --force

# 3) Verify against the gold suite (expect PASS 50/50, exit 0)
venv/bin/python eval/run_eval.py

# 4) Launch the ask-a-question UI (bilingual chat with cited sources)
venv/bin/streamlit run src/ui/app.py

# 5) Or ask from the command line
venv/bin/python -c "
from src.storage.store import get_store
from src.retrieval.router import QueryRouter
ans = QueryRouter(get_store()).answer('Combien de factures sont impayées ?')
print(ans.text)
print(ans.files)
print(ans.route)
"
```

## Project Structure

```
smebrief/
├── docs/
│   ├── ARCHITECTURE.md      # System architecture & data flow
│   ├── BUILD_PLAN.md         # Build history (incl. pivot) + remaining work + session notes
│   └── TECH_STACK.md         # Technology decisions & rationale
├── scripts/
│   └── download_models.py   # Qwen GGUF + multilingual-e5-small
├── data/
│   ├── synthetic/
│   │   ├── generator.py     # Corpus generator (manifest + gold QA + documents)
│   │   ├── manifest.json    # Single source of truth (60 docs)
│   │   ├── gold_qa.json     # 50 gold questions with answers
│   │   └── documents/       # Generated PDFs + scanned PNGs (gitignored)
│   └── smebrief.db          # SQLite store, built by ingest (gitignored)
├── eval/
│   └── run_eval.py          # 50/50 gold-QA harness
├── src/
│   ├── embeddings.py        # multilingual-e5-small helpers (offline)
│   ├── ingest/              # Corpus → store (extract, chunk, embed)
│   ├── llm/                 # llama.cpp server (lazy load, idle unload)
│   ├── ocr/                 # Legacy extraction (preprocess.py, typed.py)
│   ├── rag/                 # Retriever, context builder, LLM answers
│   ├── retrieval/           # QueryRouter — SQL intents + semantic fallback
│   ├── storage/             # SQLite schema + FinanceStore
│   └── ui/                  # Streamlit ask-a-question chat (app.py)
├── tests/                   # 36 tests: generator, ingest, router, eval, ui
├── models/                  # Downloaded models (gitignored)
├── samples/                 # Sample documents
├── requirements.txt
└── README.md
```

## License

Apache 2.0

## Built For

[Africa Deep Tech Challenge 2026](https://adtc-2026.devpost.com/) — "The Laptop LLM Challenge"
