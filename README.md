# Karatasi — Offline AI Document Processor for Kenyan Government Forms

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Karatasi** (Swahili for "paper") — an offline AI document processor that understands Kenyan government forms, extracts handwritten and typed fields, and auto-fills them. Built for the **Africa Deep Tech Challenge 2026** ("The Laptop LLM Challenge" — AI that runs on 8GB RAM laptops, offline).

```
Upload a scanned ID application form → AI detects the form type,
extracts all fields (including handwriting), and presents an editable
filled copy — all on a laptop with no internet connection.
```

---

## Why Karatasi?

Every Kenyan has filled out a government form with a pen at a crowded office desk only to be told "come back tomorrow" because of an error. Forms get rejected for bad handwriting, missing fields, or illegible copies. Internet-based solutions don't help — most Kenyans access government services from cybercafés or local offices with unreliable connectivity.

Karatasi runs entirely offline on an ordinary 8GB laptop:
- **Upload** — Scan or photo of any government form (ID application, KRA PIN, land board, birth certificate)
- **Understand** — AI detects the form type, reads printed labels with Tesseract OCR, reads handwritten content with TrOCR
- **Auto-fill** — Extracted fields appear in an editable interface in English or Swahili
- **Export** — Download a filled PDF or structured JSON

## Project Status

**Active development** — built for the Africa Deep Tech Challenge 2026 (deadline: Aug 24–25, 2026).

| Milestone | Target | Status |
|---|---|---|
| OCR pipeline (typed + handwriting) | Week 1 (Jul 29 – Aug 4) | ⬜ Not started |
| Form understanding + LLM integration | Week 2 (Aug 5 – 11) | ⬜ Not started |
| Streamlit UI + Swahili support | Week 3 (Aug 12 – 18) | ⬜ Not started |
| Polish, demo, submission | Week 4 (Aug 19 – 25) | ⬜ Not started |

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Image Processing | OpenCV | Deskew, denoise, binarize, layout detection |
| Typed OCR | Tesseract (pytesseract) | Printed label and text recognition |
| Handwriting OCR | TrOCR (Microsoft) | Handwritten field content recognition |
| LLM | Qwen2.5-1.5B-Q4_K_M (llama.cpp) | Form type identification, field extraction, structuring |
| Vector Store | FAISS | Similarity search (form templates) |
| UI | Streamlit | Self-contained web interface |
| PDF Export | ReportLab | Generate filled form PDFs |

**Memory footprint**: ~4-5GB (comfortably fits in 8GB budget)

## Quick Start

```bash
# Prerequisites: Python 3.11, Tesseract OCR installed

git clone https://github.com/kish-00/karatasi
cd karatasi

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download models (script downloads quantized LLM + TrOCR)
python scripts/download_models.py

# Run the app
streamlit run src/app.py
```

Open [http://localhost:8501](http://localhost:8501)

## Project Structure

```
karatasi/
├── docs/
│   ├── ARCHITECTURE.md      # System architecture & data flow
│   ├── BUILD_PLAN.md         # Week-by-week build plan
│   └── TECH_STACK.md         # Technology decisions & rationale
├── scripts/
│   └── download_models.py   # Model download script
├── src/
│   ├── app.py               # Streamlit entry point
│   ├── ocr/
│   │   ├── preprocess.py    # OpenCV image preprocessing
│   │   ├── typed.py         # Tesseract OCR for printed text
│   │   └── handwriting.py   # TrOCR for handwritten text
│   ├── forms/
│   │   ├── detector.py      # Form type identification
│   │   ├── templates/       # Form template definitions
│   │   └── fields.py        # Field extraction schemas
│   ├── llm/
│   │   ├── serve.py         # llama.cpp model serving
│   │   └── prompts.py       # Prompt templates
│   ├── ui/
│   │   └── components.py    # Streamlit UI components
│   └── export/
│       └── pdf.py           # PDF generation (ReportLab)
├── models/                  # Downloaded model files (gitignored)
├── samples/                 # Sample forms for testing
├── requirements.txt
└── README.md
```

## License

Apache 2.0

## Built For

[Africa Deep Tech Challenge 2026](https://adtc-2026.devpost.com/) — "The Laptop LLM Challenge"
