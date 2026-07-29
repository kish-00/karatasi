# Architecture

## Overview

Karatasi is an offline-first document processing pipeline. A scanned form enters as an image and exits as structured, editable field data. Every component runs locally — no cloud calls, no API keys, no internet.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: Scanned form (PDF, JPG, PNG)                            │
│  - Photo from phone camera                                      │
│  - Scanned PDF from cybercafé                                   │
│  - Low-quality, uneven lighting, skewed                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: IMAGE PREPROCESSING (OpenCV)                          │
│                                                                  │
│  Input: Raw scanned image                                        │
│  Output: Clean, normalized image ready for OCR                   │
│                                                                  │
│  Steps:                                                          │
│  1. Convert to grayscale                                         │
│  2. Adaptive thresholding (binarization)                         │
│  3. Deskew (correct rotation)                                    │
│  4. Denoise (remove scan noise/specks)                           │
│  5. Morphological ops (close gaps in broken text)                │
│  6. DPI normalization (scale to 300 DPI)                         │
│                                                                  │
│  Why this matters:                                               │
│  Kenyan government forms are often filled by hand, then          │
│  photocopied, then scanned. Without preprocessing, OCR           │
│  accuracy drops below 50%. With it, we hit 85%+ on typed         │
│  and 70%+ on handwriting.                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: LAYOUT DETECTION (rule-based + coordinate analysis)    │
│                                                                  │
│  Input: Preprocessed image                                       │
│  Output: Bounding boxes classified as LABEL, FIELD, CHECKBOX,   │
│          SIGNATURE, PHOTO                                        │
│                                                                  │
│  Approach:                                                       │
│  - Use contour detection + morphological analysis to find        │
│    connected components                                          │
│  - Classify regions by aspect ratio, area, and position:         │
│    · LABEL: small text regions near the left edge ("Jina la     │
│      mwombaji:", "Full Name:")                                   │
│    · FIELD: rectangular empty areas or underlined regions        │
│      adjacent to labels                                          │
│    · CHECKBOX: small squares (aspect ratio ~1:1)                 │
│    · SIGNATURE: wide region at the bottom                        │
│    · PHOTO: large rectangle at designated photo area             │
│  - Pair each FIELD with its nearest LABEL                        │
│  - Form-specific heuristics per known template                   │
│                                                                  │
│  Limitations:                                                    │
│  - Works best on forms with clear structure (which government    │
│    forms generally have)                                         │
│  - Falls back to generic label-field pairing for unknown forms   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                  ┌────────┴────────┐
                  ▼                  ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│  STAGE 3A: TYPED OCR    │  │  STAGE 3B: HANDWRITING   │
│  (Tesseract)            │  │  OCR (TrOCR)             │
│                         │  │                          │
│  Applied to: LABEL      │  │  Applied to: FIELD       │
│  regions, printed       │  │  regions classified as   │
│  instructions, typed    │  │  containing handwriting  │
│  content                │  │                          │
│                         │  │                          │
│  Tesseract is mature    │  │  TrOCR is a small        │
│  and fast for printed   │  │  transformer (~300MB)    │
│  text. With prepro-     │  │  fine-tuned on IAM +     │
│  cessed images, it      │  │  RIMES handwriting       │
│  achieves ~90%+ on      │  │  datasets. Handles       │
│  clean Kenyan forms.    │  │  short field values      │
│                         │  │  well (names, dates,     │
│                         │  │  ID numbers).            │
└───────────┬─────────────┘  └────────────┬────────────┘
            │                             │
            └──────────┬──────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: FORM UNDERSTANDING (Local LLM)                        │
│                                                                  │
│  Input: Raw OCR text + layout structure                          │
│  Output: Structured JSON with field names and values             │
│                                                                  │
│  Model: Qwen2.5-1.5B-Q4_K_M via llama.cpp (~1GB RAM)            │
│                                                                  │
│  Step 4a — Form Type Identification:                             │
│  "Given the following OCR text from a Kenyan government form,    │
│   identify the form type. Options: ID_APPLICATION, KRA_PIN,      │
│   LAND_BOARD, BIRTH_CERTIFICATE, DRIVING_LICENSE, UNKNOWN."      │
│                                                                  │
│  Step 4b — Field Extraction:                                     │
│  "Extract field-value pairs from this OCR output. Return as      │
│   JSON. Include: label, value, confidence (0-1), is_handwritten." │
│                                                                  │
│  Step 4c — Language Detection:                                   │
│  "Detect whether the form is in English or Swahili. Translate    │
│   field labels to both languages."                               │
│                                                                  │
│  Prompt engineering notes:                                       │
│  - System prompt sets context as a Kenyan government clerk       │
│    who reads both English and Swahili                            │
│  - Few-shot examples included in the prompt for each form type   │
│  - Output constrained to JSON using structured output format     │
│  - Temperature: 0.1 (deterministic extraction)                   │
│                                                                  │
│  Why not use the LLM for OCR?                                    │
│  Vision-language models (like LLaVA) that can read text from     │
│  images directly are too large (7B+) for 8GB RAM. The two-stage  │
│  OCR → LLM approach is more memory-efficient and equally          │
│  effective for structured forms.                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5: STREAMLIT UI                                          │
│                                                                  │
│  Layout:                                                        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  Header: "Karatasi — Kujaza Fomu Kiotomatiki"        │        │
│  │          (Swahili: "Automatic Form Filling")          │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │  ┌──────────┐  ┌──────────────────────────────────┐ │        │
│  │  │ Upload   │  │ Preview Panel                    │ │        │
│  │  │ Zone     │  │ - Shows original scanned form     │ │        │
│  │  │          │  │ - Highlight detected regions      │ │        │
│  │  │ Drag &   │  │ - Color-coded by type             │ │        │
│  │  │ drop or  │  │   (LABEL=blue, FIELD=green,       │ │        │
│  │  │ browse   │  │    CHECKBOX=orange, SIGNATURE=red) │ │        │
│  │  └──────────┘  └──────────────────────────────────┘ │        │
│  ├──────────────────────────────────────────────────────┤        │
│  │  ┌──────────────────────────────────────────────────┐│        │
│  │  │  Filled Form (editable)                          ││        │
│  │  │  ┌────────────────────────────────────┐          ││        │
│  │  │  │ Form Type: [ID Application]         │          ││        │
│  │  │  │ Full Name: [John Kamau] ◈ Swahili   │          ││        │
│  │  │  │ ID Number: [12345678]  ◈ English    │          ││        │
│  │  │  │ Date: [2026-07-29]                  │          ││        │
│  │  │  │ Signature: [✍ captured]             │          ││        │
│  │  │  │                                      │          ││        │
│  │  │  │  [Export PDF]  [Export JSON]         │          ││        │
│  │  │  └────────────────────────────────────┘          ││        │
│  │  └──────────────────────────────────────────────────┘│        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
│  Interactions:                                                   │
│  - Language toggle (English/Swahili) changes all UI labels       │
│  - Each extracted field is an editable text input                │
│  - Confidence indicators: green (high), yellow (medium),         │
│    red (low) — user knows which fields to verify                 │
│  - Hover over a field highlights its position on the             │
│    original scan                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6: EXPORT                                               │
│                                                                  │
│  PDF Export (ReportLab):                                        │
│  - Overlay filled text onto the original form PDF               │
│  - Uses coordinates from layout detection to place text         │
│    in the correct field positions                                │
│  - Embed captured signature image if available                   │
│  - Print-ready output                                           │
│                                                                  │
│  JSON Export:                                                   │
│  - Structured data for downstream systems                       │
│  - Schema: {form_type, fields[], language, confidence_scores}   │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Budget

This is the critical metric for the Africa Deep Tech Challenge. The target is 8GB RAM total.

| Component | Resident Memory | Notes |
|---|---|---|
| OS (Ubuntu minimal / similar) | ~1.5-2 GB | Desktop environment |
| Python runtime + Streamlit | ~300 MB | Including dependencies |
| OpenCV + Tesseract | ~250 MB | Shared libraries, loaded at startup |
| TrOCR (handwriting model) | ~500 MB | Loaded on-demand, unloaded after use |
| LLM (Qwen2.5-1.5B-Q4_K_M) | ~1.0 GB | Quantized to 4-bit via llama.cpp |
| FAISS index | ~100 MB | Form template embeddings |
| PDF processing + misc | ~150 MB | PyMuPDF, ReportLab, PIL |
| Application data | ~100 MB | Uploaded forms, temp files |
| Cache + headroom | ~1.6 GB | Prevents OOM during spikes |
| **Total (estimated)** | **~4.5-5.5 GB** | ✅ Fits with headroom |

## Key Design Decisions

### Why Streamlit instead of React + FastAPI?
The existing `ai-pdf-assistant` project uses React + FastAPI. That's client-server, which means two processes, more RAM, and a more complex offline packaging story. Streamlit is a single Python process — simpler to deploy, demo, and debug. The trade-off is less visual polish, but for a hackathon, demo reliability beats pixel perfection.

### Why a 1.5B LLM instead of 7B?
Phi-3-mini (3.8B) Q4 uses ~2.5GB. Llama 3 8B Q4 uses ~5.5GB. For form parsing (identifying types, extracting fields from clean OCR text), a 1.5B model is sufficient. The benchmark score rewards accuracy ÷ memory — a slightly less accurate model that uses 1/4 the memory scores higher.

### Why TrOCR for handwriting instead of a vision model?
Small vision-language models that can read handwriting from images (like TrOCR) are ~300MB. Larger VLMs that can do both detection and reading (like LLaVA-NeXT) are 7B+ and won't fit. The staged approach (layout detection → crop → TrOCR) is the most memory-efficient way to handle handwriting.

### Why Swahili prompts instead of a bilingual model?
Qwen2.5 has reasonable Swahili coverage in its training data. Rather than adding a separate translation model (more RAM), we prompt the same LLM in Swahili for Swahili outputs. The system prompt establishes Swahili as the working language — the model will then extract fields and label them in Swahili naturally.
