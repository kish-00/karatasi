# Build Plan — Africa Deep Tech Challenge 2026

**Deadline**: Aug 24–25, 2026
**Start date**: Jul 29, 2026
**Total time**: 4 weeks

## Week 1 (Jul 29 – Aug 4): OCR Pipeline

### Goal
Working OCR pipeline: upload a scanned form → preprocessed image → extracted text (typed + handwriting).

### Tasks

**Day 1-2: Environment + Image Preprocessing**
- [x] Set up Python venv, install dependencies (OpenCV, pytesseract, torch, transformers)
- [x] Install Tesseract OCR system package (bundled in venv via .deb extraction)
- [x] Build `src/ocr/preprocess.py`:
  - Grayscale conversion
  - Adaptive thresholding (Gaussian adaptive, blockSize=31)
  - Deskew (minAreaRect on text contours)
  - Denoise (Gaussian blur 3x3 + morphological close)
  - DPI normalization (target 300 DPI)
  - Web-portal PDF detection (`is_web_portal()`)
- [x] Test on 5 scanned Kenyan forms:
  - Form 1 (ID App): 344ms → 148 regions
  - Form 2 (Land Board): 233ms → 84 regions
  - Form 3 (Birth B4): 73ms → web portal
  - Form 4 (Birth B3): 195ms → 65 regions
  - Form 5 (Birth A1): 69ms → web portal
- [x] Measure: preprocessing in **60–400ms** (target: <3s)

**Day 3: Typed OCR (Tesseract)**
- [x] Build `src/ocr/typed.py`:
  - pytesseract wrapper (PSM 3 for full page, PSM 6 for regions)
  - Region-of-interest cropping from layout detection
  - Per-segment confidence scoring
  - Coordinate-space handling (scale_to_original parameter)
- [x] Test on form labels: recall ~9/15 labels with text after coordinate fix
- [x] Measure: full-page OCR in **~11s**, label OCR **~900ms** on 200 DPI scans

**Day 4: Handwriting OCR (TrOCR)**
- [x] Build `src/ocr/handwriting.py`:
  - TrOCR base handwritten model (microsoft/trocr-base-handwritten)
  - Local model directory resolution (`_get_model_path()`)
  - Lazy loading with caching (model stays loaded by default)
  - Explicit `unload_model()` for memory management
- [x] Test on field crops from 5 forms (first inference ~17s model load, subsequent ~1-5s)
- [x] Caching: model stays loaded after first call → subseq. calls **~1-5s**

**Day 5: Layout Detection**
- [x] Build layout analysis in `src/ocr/preprocess.py`:
  - Contour detection → bounding boxes
  - Classify regions (label, field, checkbox, signature, photo)
  - Pair labels with adjacent fields
  - Coordinate-space selection (scale_to_original for display, preprocessed-space for OCR)
- [x] Min-size label filter (w>=30, h>=15) removes false-positive noise regions
- [x] Integration test: full pipeline on 5 forms (2 correctly identified as web portal)

### Deliverables
- ✅ Functional OCR module with `detect_layout()`, `ocr_image()`, `recognize_handwriting()`
- ✅ Tested on 5 Kenyan government form scans (3 real forms + 2 web-portal PDFs)
- ✅ Fast-path memory: **<500MB** for OCR pipeline (excluding LLM/TrOCR)

---

## Week 2 (Aug 5 – 11): Form Understanding

### Goal
Form type detection + field extraction + unified pipeline → structured output under 12s.

### Tasks

**Day 6: LLM Setup**
- [x] Set up llama.cpp Python bindings (llama-cpp-python)
- [x] Download Qwen2.5-1.5B-Q4_K_M GGUF model (1117MB)
- [x] Build `src/llm/serve.py`:
  - Model loader with lazy init + mmap
  - Context window: 2048 tokens
  - Automatic model unloading after 5min idle
  - `get_server()` singleton accessor
- [x] Benchmark: 2.9s per inference, 7 tok/s, ~2.5GB RAM

**Day 7: Prompt Engineering — Form Type & Field Extraction**
- [x] Build `src/llm/prompts.py` with system prompt templates:
  - System prompt: Kenyan government clerk persona (English + Swahili)
  - Form type classifier prompt (shortened for 1.5B model)
  - Field extraction prompt (ultra-minimal: OCR + labels + JSON-only output)
  - Language detection prompt
- [x] Build `src/forms/detector.py`:
  - `detect_form_type(ocr_text, use_llm=False)` — keyword detection as primary
  - Regex patterns for 7 form types: ID_APPLICATION, LAND_BOARD, BIRTH_CERTIFICATE, BIRTH_LATE_REGISTRATION, BIRTH_REGISTRATION, KRA_PIN, DRIVING_LICENSE, UNKNOWN
  - Confidence scoring: 0.50 + 0.15 per matched keyword (cap 0.90)
  - LLM fallback when `use_llm=True` (disabled by default)
  - Robust JSON parsing: finds `{...}` anywhere in verbose LLM output
- [x] Test on 5 form samples → **100% classification accuracy** via keywords (0.90+ confidence)

**Day 8: Form Templates**
- [x] Build field schemas inline in `src/forms/fields.py`:
  - `ExtractedField` dataclass (key, label_en, label_sw, value, confidence, field_type, is_handwritten)
  - `FieldSchema` dataclass (key, label_en, label_sw, field_type, validation, required)
  - 4 form templates:
    - **ID_APPLICATION**: 14 fields (serial_no, surname, first_name, other_names, date_of_birth, place_of_birth, district_of_birth, sex, height, occupation, marital_status, residence, signature, photo)
    - **LAND_BOARD**: 8 fields (applicant_name, id_number, property_description, property_location, consent_type, consideration, signature, date)
    - **BIRTH_LATE_REGISTRATION**: 11 fields (child_name, date_of_birth, place_of_birth, sex, father_name, mother_name, father_id, mother_id, informant_name, signature, date_registered)
    - **BIRTH_CERTIFICATE**: 7 fields (child_name, date_of_birth, place_of_birth, sex, father_name, mother_name, registration_number)
  - Validation rules: required, id_number (6-8 digits), phone (0XXXXXXXXX), date (DD/MM/YYYY), email, number
  - `validate_field()` function per rule

**Day 9: Field Extraction Pipeline**
- [x] Template-based extraction: `extract_fields(ocr_text, form_type, use_llm=False)` → fields with empty values
- [x] LLM extraction: `extract_fields(ocr_text, form_type, use_llm=True)` → LLM fills values (disabled by default)
- [x] `_merge_llm_with_template()` — template order preserved, LLM values merged
- [x] `_parse_json_array()` — finds `[...]` anywhere in LLM output (handles markdown fences, leading text)
- [x] `_template_fallback()` — returns template fields with empty values and 0.0 confidence
- [x] Edge cases: blank form (all fields empty), web portal (early return), unknown form type (no fields)

**Day 10: Integration + Benchmark**
- [x] Build `src/pipeline.py` — `process_form()` unified pipeline:
  1. Load + preprocess (60-400ms)
  2. Tesseract full-page OCR (~11s)
  3. Web portal detection (early return if portal page)
  4. Layout detection in preprocessed-space
  5. Form type detection via keywords (<10ms)
  6. Template field extraction (<1ms)
  7. Optional TrOCR handwriting on field regions (disabled by default, ~70s)
- [x] `use_llm` and `use_trocr` as independent boolean flags (both default False)
- [x] Printed-text filter in TrOCR: cross-checks output against Tesseract full-page text
- [x] Ink-ratio guard: skips nearly blank field regions (<1% dark pixels)
- [x] End-to-end test on 5 samples:
  - Form 1 (ID App): 11.5s, 14 fields empty (blank form) ✅
  - Form 2 (Land Board): 8.4s, 8 fields empty ✅
  - Form 3 (Birth B4): 1.0s, web portal detected ✅
  - Form 4 (Birth B3): 12.7s, 11 fields empty ✅
  - Form 5 (Birth A1): 1.1s, web portal detected ✅
- [x] No garbage values — printed-text filter + ink-ratio guard + disabled TrOCR default eliminates false readings
- [x] Benchmark: 3 runs, **avg 11.4s per form** (target: <30s) ✅
- [x] Bottleneck identified: Tesseract OCR at 97% of pipeline time (10.9s)

### Actual vs Planned

| Item | Planned | Actual |
|---|---|---|
| Form type detection accuracy | >90% | **100%** (5/5 via keywords) |
| Field extraction accuracy | >80% | **N/A on blank forms** (no handwriting test data available) |
| Pipeline speed | <30s | **11.4s avg** (fast path) |
| LLM inference | <5s | **2.9s** per call, but 45-85s for end-to-end field extraction |
| Templates | 4+ | **4** (ID_APPLICATION, LAND_BOARD, BIRTH_LATE_REG, BIRTH_CERT) |
| LLM usage | Primary classifier | **Disabled by default** — keywords are faster and more reliable |

### Key Lessons
1. **Keywords beat 1.5B LLM for form type detection** — 100% accuracy in <10ms vs 45-85s with hallucination risk
2. **Tesseract is the pipeline bottleneck** at 97% of total time (~11s). No viable faster alternative for offline printed OCR.
3. **Blank forms produce garbage with TrOCR** — form labels get read as "handwriting". Fix: printed-text filter using Tesseract full-page text overlap, plus ink-ratio check.
4. **Small LLMs fabricate data** — the 1.5B model returns "1990-01-01" for a blank date field. Template-with-empty-values is the correct deterministic approach.
5. **Separate `use_trocr` from `use_llm`** — they serve independent purposes (image-to-text vs text understanding).

### Deliverables
- ✅ Unified pipeline: scanned form → structured fields (11.4s fast path)
- ✅ Form type detection via keywords (100% accuracy on test set)
- ✅ 4 form templates defined with field schemas + validation
- ✅ Optional TrOCR handwriting with printed-text filter + ink-ratio guard
- ✅ Optional LLM field extraction (disabled by default)
- ✅ Memory (fast path): **<500MB** (TrOCR/LLM add 1.5-4GB when enabled)

---

## Week 3 (Aug 12 – 18): Streamlit UI + Swahili

### Goal
Self-contained Streamlit application with English/Swahili interface, editable fields, and export.

### Tasks

**Day 11: Streamlit Shell**
- [ ] Build `src/app.py` — main Streamlit app
- [ ] File upload widget (PDF, JPG, PNG) with drag-and-drop
- [ ] Language selector (English/Swahili) — persists across reruns
- [ ] Session state management for form data across interactions
- [ ] `src/ui/components.py` — reusable UI components

**Day 12: Preview + Results**
- [ ] Original form preview panel (image display)
- [ ] Detected regions overlay (bounding boxes color-coded by type)
- [ ] Extracted fields display:
  - Editable text inputs for each field
  - Confidence indicator (colored dot: green/yellow/red)
  - "Verified" checkbox per field
- [ ] Form type selector (if auto-detection is wrong, user can override)

**Day 13: Swahili UI**
- [ ] Language strings file (`src/ui/strings.py`):
  - All UI text in English + Swahili
  - Field label translations (e.g., "Full Name" → "Jina Kamili")
  - Error messages, tooltips, button labels
- [ ] Language toggle switches all UI text dynamically
- [ ] Swahili prompt mode: when Swahili is selected, LLM prompts are in Swahili

**Day 14: Export**
- [ ] `src/export/pdf.py` — PDF generation:
  - Overlay text onto original form coordinates
  - Font choice: DejaVu Sans (supports Swahili characters)
  - Signature image embedding
- [ ] JSON export: form data as structured JSON file
- [ ] Download buttons in Streamlit

**Day 15-16: Polish + Buffer**
- [ ] Loading states and progress indicators
- [ ] Error handling (bad scans, wrong orientation, unsupported forms)
- [ ] Performance optimization (model loading, caching, lazy evaluation)
- [ ] Responsive layout (works on 1366x768 laptop screens)
- [ ] Package as single-launch command

### Deliverables
- Working Streamlit app with full UI
- English + Swahili language support
- PDF and JSON export working
- Total app memory: <5.5GB

---

## Week 4 (Aug 19 – 25): Polish + Submission

### Goal
Demo-ready application that judges can run on an 8GB laptop.

### Tasks

**Day 17-18: Real-World Testing**
- [ ] Find 5 people who have filled Kenyan government forms recently
- [ ] Have them test the app with their actual forms (photos on phone)
- [ ] Collect failure cases and fix:
  - Poor lighting → improve preprocessing
  - Non-English handwriting → expand TrOCR
  - Unknown form types → improve template fallback
- [ ] Measure end-to-end time and accuracy

**Day 19: Performance Tuning**
- [ ] Memory optimization:
  - Profile memory usage with `memory_profiler`
  - Implement model unloading aggressively
  - Stream image processing (avoid loading full HD images)
  - Use lazy imports
- [ ] Speed optimization:
  - Cache OCR results for same image
  - Parallelize Tesseract + TrOCR
  - LLM batching

**Day 20: Edge Cases + error handling**
- [ ] Handle:
  - 10MB+ scanned files (downscale)
  - Rotated/upside-down pages (auto-rotate)
  - Multipage forms (process page by page)
  - Blurry/low-res photos (warning + suggestion)
  - Non-form uploads (reject gracefully)
- [ ] Comprehensive error messages in both languages
- [ ] Fallback paths for every failure mode

**Day 21: Demo Preparation**
- [ ] Record 3-minute demo video (required for submission)
  - Script: problem → upload → auto-detection → edit → export
  - Show Swahili toggle
  - Show confidence indicators
  - Run on actual 8GB laptop (record with OBS)
- [ ] Write README with screenshots
- [ ] Write Devpost submission:
  - Project description
  - How it works (technical)
  - Challenges faced
  - What's next
- [ ] Package as `pip install -r requirements.txt` + `streamlit run src/app.py`

**Day 22-23: Buffer + Polish**
- [ ] Fix any remaining bugs
- [ ] Test on clean 8GB laptop installation
- [ ] Polish README
- [ ] Submit to Devpost

**Day 24: Deadline (Aug 24-25)**
- [ ] Final submission on Devpost
- [ ] Ensure video is uploaded and visible
- [ ] Confirm all submission fields complete

### Deliverables
- Fully functional offline application
- Demo video (3 min)
- Devpost submission
- Public GitHub repository

---

## Success Criteria

| Metric | Target | Current | How to Measure |
|---|---|---|---|
| Form type detection accuracy | >90% | **100%** (5/5) | Test on 20 labeled forms |
| Field extraction accuracy | >80% | N/A (no filled forms yet) | Compare extracted vs manual entry on 10 forms |
| Memory usage (fast path) | <6GB | **<500MB** | `free -h` while running |
| Memory usage (all models) | <6GB | **~4-7GB** (swap risk) | `free -h` while running |
| Pipeline speed | <30s | **11.4s avg** (fast path) | Stopwatch per form |
| Swahili support | All UI + outputs | **Not yet built** | Manual review |
| One-command launch | Yes | **Not yet** (CLI only) | Test on clean machine |
