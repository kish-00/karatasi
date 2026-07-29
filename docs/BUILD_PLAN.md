# Build Plan — Africa Deep Tech Challenge 2026

**Deadline**: Aug 24–25, 2026
**Start date**: Jul 29, 2026
**Total time**: 4 weeks

## Week 1 (Jul 29 – Aug 4): OCR Pipeline

### Goal
Working OCR pipeline: upload a scanned form → preprocessed image → extracted text (typed + handwriting).

### Tasks

**Day 1-2: Environment + Image Preprocessing**
- [ ] Set up Python venv, install dependencies (OpenCV, pytesseract, torch, transformers)
- [ ] Install Tesseract OCR system package + Swahili language pack
- [ ] Build `src/ocr/preprocess.py`:
  - Grayscale conversion
  - Adaptive thresholding (Otsu's method)
  - Deskew (Hough transform or minAreaRect)
  - Denoise (Gaussian blur + morphological ops)
  - DPI normalization
- [ ] Test on 5 scanned Kenyan forms (varying quality)
- [ ] Measure: preprocessing → readable image in <3 seconds

**Day 3: Typed OCR (Tesseract)**
- [ ] Build `src/ocr/typed.py`:
  - pytesseract wrapper with optimized config (`--psm 6 --oem 3`)
  - Region-of-interest cropping from layout detection
  - Confidence scoring per text segment
  - Swahili character support (add `-l eng+swk`)
- [ ] Test on 10 scanned form labels
- [ ] Measure: >85% character accuracy on typed text

**Day 4: Handwriting OCR (TrOCR)**
- [ ] Build `src/ocr/handwriting.py`:
  - TrOCR small model (microsoft/trocr-base-handwritten)
  - Crop field regions → run inference → return text
  - Lazy loading (model loads only when handwriting detected)
  - Model unloads after inference to free memory
- [ ] Test on handwritten fields from 5 forms
- [ ] Measure: >65% accuracy on short handwritten fields (names, numbers)

**Day 5: Layout Detection**
- [ ] Build layout analysis in `src/ocr/preprocess.py`:
  - Contour detection → bounding boxes
  - Classify regions (label, field, checkbox, signature, photo)
  - Pair labels with adjacent fields
  - Form-specific heuristics per template
- [ ] Fallback: generic label-field pairing for unknown forms
- [ ] Integration test: full pipeline end-to-end on 3 forms

### Deliverables
- Functional OCR module with `process_image(path) -> {"labels": [...], "fields": [...], "handwriting": [...]}`
- Tested on at least 5 Kenyan government form scans
- Memory usage: <1.5GB (excluding LLM)

---

## Week 2 (Aug 5 – 11): Form Understanding

### Goal
Local LLM serving + form type detection + field extraction → structured JSON output.

### Tasks

**Day 6: LLM Setup**
- [ ] Set up llama.cpp Python bindings (llama-cpp-python)
- [ ] Download Qwen2.5-1.5B-Q4_K_M GGUF model
- [ ] Build `src/llm/serve.py`:
  - Model loader with memory-efficient config
  - Context window: 2048 tokens
  - Batch inference for multiple fields
  - Automatic model unloading after idle timeout
- [ ] Benchmark: <5 seconds per inference, <1.5GB RAM

**Day 7: Prompt Engineering — Form Type Detection**
- [ ] Build `src/llm/prompts.py` with system prompt templates:
  - System prompt: Kenyan government clerk persona (English + Swahili)
  - Form type classifier prompt
  - Field extraction prompt
  - Swahili translation prompt
- [ ] Implement few-shot examples per form type (3 examples each)
- [ ] Build `src/forms/detector.py`:
  - `detect_form_type(ocr_text) -> {"form_type": str, "confidence": float}`
- [ ] Test on 10 form samples → >90% classification accuracy

**Day 8: Form Templates**
- [ ] Build template definitions in `src/forms/templates/`:
  - `id_application.py` — Kenyan National ID application form
  - `kra_pin.py` — KRA PIN registration form
  - `land_board.py` — Land control board consent form
  - `birth_certificate.py` — Birth certificate application
  - Each template: expected labels, field positions, validation rules,
    Swahili translations
- [ ] Build `src/forms/fields.py`:
  - Field extraction schema (label, value, confidence, coords, is_handwritten)
  - Validation rules per field type (ID number format, phone format, date)
  - Confidence aggregation

**Day 9: Field Extraction Pipeline**
- [ ] Wire LLM to form templates:
  - OCR output → LLM form type detection → select template → LLM field extraction
- [ ] Structured output parsing (regex + JSON parsing with error recovery)
- [ ] Confidence scoring: combine OCR confidence + LLM confidence
- [ ] Edge cases: missing fields, extra text, torn corners

**Day 10: Integration + Buffer**
- [ ] Integrate Week 1 (OCR) + Week 2 (LLM) into unified pipeline
- [ ] End-to-end test: scan → JSON output on 10 forms
- [ ] Fix issues, refine prompts, tune thresholds
- [ ] Benchmark total pipeline time: <30 seconds per form

### Deliverables
- End-to-end pipeline: scanned form → structured JSON
- 4 form templates defined and tested
- Classification accuracy: >90%, field extraction: >80%

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

| Metric | Target | How to Measure |
|---|---|---|
| Form type detection accuracy | >90% | Test on 20 labeled forms |
| Field extraction accuracy | >80% | Compare extracted vs manual entry on 10 forms |
| Memory usage | <6GB | `free -h` while running |
| Inference speed | <30s per form | Stopwatch from upload to results |
| Swahili support | All UI + outputs | Manual review |
| One-command launch | Yes | Test on clean machine |
