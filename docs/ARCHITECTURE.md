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
│  STAGE 1.5: WEB PORTAL DETECTION                                 │
│                                                                  │
│  Some PDFs are not scanned forms but web portal printouts        │
│  (e.g., "Enable JavaScript and cookies to continue").            │
│  `is_web_portal()` checks the raw OCR text for known             │
│  portal-only phrases and returns early if matched.               │
│                                                                  │
│  This saves the user from waiting through layout detection       │
│  + LLM inference on an unprocessable file.                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: LAYOUT DETECTION (rule-based + coordinate analysis)    │
│                                                                  │
│  Input: Preprocessed image                                       │
│  Output: Bounding boxes classified as text, field, table,        │
│          table_cell                                              │
│                                                                  │
│  Approach:                                                       │
│  - Use contour detection + morphological analysis to find        │
│    connected components                                          │
│  - Classify regions by aspect ratio, area, and position          │
│  - Coordinate-space parameter: `scale_to_original=False` for     │
│    OCR cropping (preprocessed-space), `scale_to_original=True`   │
│    for display overlays (original image coordinates)             │
│                                                                  │
│  Limitations:                                                    │
│  - Works best on forms with clear structure (which government    │
│    forms generally have)                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3A: TYPED OCR (Tesseract)                                 │
│                                                                  │
│  Applied to: full page (PSM 3), then optionally to individual    │
│  regions (PSM 6).                                                │
│                                                                  │
│  Tesseract is mature and fast for printed text. With             │
│  preprocessed images, it achieves ~90%+ on clean Kenyan forms.   │
│  Swahili uses `-l eng` (Latin script, no Swahili traineddata     │
│  available in standard distribution).                            │
│                                                                  │
│  Performance: full-page OCR in ~10.9s on 200 DPI scans           │
│  (dominant pipeline bottleneck at ~97% of total time).           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3B: HANDWRITING OCR — TrOCR (optional, disabled default)  │
│                                                                  │
│  Applied to: field regions from layout detection (only when      │
│  `use_trocr=True`).                                              │
│                                                                  │
│  TrOCR is a small transformer (~330M params) fine-tuned on      │
│  IAM + RIMES handwriting datasets. Handles short field values    │
│  well (names, dates, ID numbers).                                │
│                                                                  │
│  Guards against garbage:                                        │
│  - Printed-text filter: if TrOCR output matches Tesseract        │
│    full-page text, it's a form label — skip (not handwriting)    │
│  - Ink-ratio check: skip nearly blank regions (<1% dark pixels)  │
│  - Minimum confidence bar: only accept TrOCR output >0.6         │
│                                                                  │
│  Performance: ~70s for 14 field regions on CPU.                  │
│  Disabled by default; enable with `use_trocr=True`.              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: FORM UNDERSTANDING (keyword + optional LLM)            │
│                                                                  │
│  Input: Raw OCR text + form type                                 │
│  Output: Structured list of ExtractedField with values           │
│                                                                  │
│  Step 4a — Form Type Identification (keyword, <10ms):           │
│  Regex patterns match known form keywords:                      │
│    "Reg. 136 A" + "registration of persons act" → ID_APPLICATION │
│    "land control act" + "consent of land"       → LAND_BOARD     │
│    "form b3" + "late registration"              → BIRTH_LATE_REG │
│    "kra pin" + "itax"                           → KRA_PIN        │
│    etc. for DRIVING_LICENSE, BIRTH_CERTIFICATE, BIRTH_REGISTRATION│
│  Confidence: starts at 0.50 + 0.15 per matched keyword (cap 0.90)│
│  This is the PRIMARY detector — fast, deterministic, offline.    │
│                                                                  │
│  Step 4b — LLM Fallback (optional, `use_llm=True`):             │
│  Qwen2.5-1.5B-Q4_K_M via llama.cpp (~2.5GB RAM, mmapped).      │
│  Used only when keyword confidence < 0.80 (rare; all 5 test      │
│  forms hit 0.90+ via keywords).                                  │
│                                                                  │
│  Step 4c — Field Extraction (template-based, <1ms):             │
│  Each form type has a template of expected FieldSchema:          │
│    ID_APPLICATION:        14 fields (surname, first_name, DOB…)  │
│    LAND_BOARD:             8 fields (applicant_name, property…)  │
│    BIRTH_LATE_REGISTRATION: 11 fields (child_name, father_name…) │
│    BIRTH_CERTIFICATE:      7 fields (child_name, DOB, sex…)     │
│                                                                  │
│  Step 4d — LLM Field Extraction (optional, `use_llm=True`):     │
│  Prompt includes OCR text + known labels. Returns JSON array.    │
│  Parsing handles markdown fences, inline text before/after JSON. │
│  Disabled by default due to:                                     │
│  - 45-85s inference time on 1.5B model (vs <1ms template)        │
│  - Hallucinates values on blank forms                            │
│  - 1.5B model fails to follow JSON-only formatting instructions  │
│                                                                  │
│  Why not use the LLM for everything?                             │
│  The 1.5B Qwen2.5 model is too slow and unreliable for primary   │
│  extraction. Keyword detection + template fallback is faster,    │
│  more reliable, and deterministic. The LLM is reserved for       │
│  ambiguous cases or future enhancement.                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5: STREAMLIT UI (Week 3 — not yet built)                  │
│                                                                  │
│  Layout:                                                         │
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
│  STAGE 6: EXPORT (Week 3 — not yet built)                       │
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
| Python runtime + pip deps | ~300 MB | torch CPU is heaviest dependency |
| OpenCV + Tesseract | ~250 MB | Shared libraries, loaded at startup |
| TrOCR (handwriting model) | ~1.5 GB | PyTorch transformer (~300MB weights + runtime) |
| LLM (Qwen2.5-1.5B-Q4_K_M) | ~2.5 GB | llama.cpp with mmap |
| FAISS + sentence-transformers | ~150 MB | Not yet implemented |
| PDF processing + misc | ~150 MB | PyMuPDF, ReportLab, PIL |
| Application data | ~100 MB | Uploaded forms, temp files |
| Cache + headroom | ~1.5 GB | Prevents OOM during spikes |
| **Total (TrOCR + LLM loaded)** | **~6.0-7.0 GB** | Tight — may use swap |
| **Fast path (no LLM, no TrOCR)** | **~2.5 GB** | ✅ Comfortably fits |

## Key Design Decisions

### Why keyword detection instead of LLM for form type?
Keyword matching with regex patterns achieves 0.90+ confidence in <10ms for all 5 test forms. The LLM (Qwen2.5-1.5B) takes 45-85s and is less reliable (ignores JSON-only formatting instruction). For deterministic structured tasks on known forms, keyword matching wins.

### Why templates instead of LLM for field extraction?
The 1.5B model hallucinates values on blank forms (e.g., "1990-01-01" for a blank date field). Template-based extraction returns empty fields with correct labels — deterministic, zero tokens, <1ms. The LLM is reserved for ambiguous cases or future filled-form enhancement.

### Why Streamlit instead of React + FastAPI?
The existing `ai-pdf-assistant` project uses React + FastAPI. That's client-server, which means two processes, more RAM, and a more complex offline packaging story. Streamlit is a single Python process — simpler to deploy, demo, and debug. The trade-off is less visual polish, but for a hackathon, demo reliability beats pixel perfection.

### Why a 1.5B LLM instead of 7B?
Phi-3-mini (3.8B) Q4 uses ~2.5GB. Llama 3 8B Q4 uses ~5.5GB. For form parsing (identifying types, extracting fields from clean OCR text), a 1.5B model is sufficient. The benchmark score rewards accuracy ÷ memory — a slightly less accurate model that uses 1/4 the memory scores higher.

### Why TrOCR for handwriting instead of a vision model?
Small vision-language models that can read handwriting from images (like TrOCR) are ~300MB weights. Larger VLMs that can do both detection and reading (like LLaVA-NeXT) are 7B+ and won't fit. The staged approach (layout detection → crop → TrOCR) is the most memory-efficient way to handle handwriting. Note that PyTorch adds ~1GB runtime overhead beyond the model weights.

### Why `use_llm` and `use_trocr` are separate flags?
They serve independent purposes: LLM for structured text understanding (form type, field extraction) and TrOCR for image-to-text (handwriting reading). Both are disabled by default to keep the fast path under 12s. Users explicitly enable them for filled forms or ambiguous cases.
