# Technology Stack — Decisions & Rationale

Every choice in Karatasi is driven by one constraint: **must run offline on an 8GB RAM laptop**. This document explains why each technology was chosen and what the alternatives were.

---

## Image Processing

**Chosen**: OpenCV (cv2) via opencv-python-headless
**Alternative**: PIL/Pillow, scikit-image

OpenCV is the standard for document image processing. It's fast (C++ backend with Python bindings), memory-efficient (~100MB resident), and has every preprocessing function we need built in. PIL is simpler but lacks advanced deskew, adaptive thresholding, and morphological operations.

```
Key OpenCV functions used:
- cv2.adaptiveThreshold() — binarization for varied lighting
- cv2.getRotationMatrix2D() + warpAffine() — deskew
- cv2.morphologyEx() — close gaps, remove noise
- cv2.findContours() — layout detection
```

---

## OCR — Printed Text

**Chosen**: Tesseract 5 (pytesseract, via opencv-python-headless)
**Alternative**: EasyOCR, PaddleOCR, Surya

Tesseract is the only mature, offline, open-source OCR engine with Swahili language support. EasyOCR and PaddleOCR are more accurate for handwriting but are 2-3x heavier (GPU-dependent). Surya is more modern but requires significant VRAM.

| Feature | Tesseract | EasyOCR | PaddleOCR | Surya |
|---|---|---|---|---|
| Offline | ✅ | ✅ | ✅ | ✅ |
| Swahili support | ✅ (Latin script, `-l eng`) | ❌ | ❌ | ❌ |
| RAM usage | ~150MB | ~800MB | ~1GB | ~2GB |
| Speed (full page) | ~11s on CPU | Very slow | Medium | Slow |
| Handwriting | Poor | Good | Medium | Good |

Tesseract wins for our use case because most form *labels* are printed (clear, consistent font). 97% of pipeline time is Tesseract — it is the dominant bottleneck.

**Swahili note**: Standard Tesseract distributions lack `swk` (Swahili) traineddata. Swahili uses Latin script, so the English model (`-l eng`) handles it with acceptable accuracy. A dedicated Swahili traineddata file would improve accuracy for Swahili-specific letters but is not available.

---

## OCR — Handwritten Text

**Chosen**: TrOCR (microsoft/trocr-base-handwritten)
**Alternative**: TrOCR small, TrOCR large, PaddleOCR handwriting, No handwriting support

TrOCR is a transformer-based handwriting recognition model (~330M parameters, ~300MB checkpoint). It's designed for single-line text recognition from cropped images. We crop handwritten fields using layout detection, then run TrOCR on each field individually.

```
Model: microsoft/trocr-base-handwritten
Size: ~300MB (PyTorch checkpoint)
Accuracy on English handwriting: ~80% (short phrases)
RAM usage: ~1.5GB (PyTorch weights + runtime overhead)
Inference speed: ~5s per field region on CPU (14 fields → ~70s)
```

**Disabled by default**: TrOCR reads form labels as "handwriting" on blank forms, producing garbage. A printed-text filter (cross-references output against Tesseract full-page text) and ink-ratio guard (<1% dark pixels → skip) mitigate this. Enable with `use_trocr=True`.

**Memory note**: While the model checkpoint is ~300MB, PyTorch adds significant runtime overhead (~1.2GB). Total TrOCR memory footprint is ~1.5GB when loaded.

**Why not a vision-language model (VLM)?**
VLMs like LLaVA, Qwen-VL, or CogVLM can read handwriting in context but are 7B+ parameters and won't fit in 8GB alongside the rest of the pipeline. The staged approach (crop → TrOCR) is more memory-efficient.

**Why not PaddleOCR?**
PaddleOCR's handwriting recognition module requires GPU for acceptable speed and has no Swahili support.

---

## LLM — Form Understanding

**Chosen**: Qwen2.5-1.5B (Q4_K_M quantization via llama.cpp)
**Alternative**: Phi-3-mini, Gemma-2-2B, Llama 3.2-1B/3B

| Model | Parameters | Quantized Size | RAM Usage | Form Parsing Quality |
|---|---|---|---|---|
| **Qwen2.5-1.5B** | 1.5B | ~1.1 GB | ~2.5 GB | Good |
| Llama 3.2-1B | 1B | ~700 MB | ~1.5 GB | Acceptable |
| Gemma-2-2B | 2B | ~1.3 GB | ~2.5 GB | Good |
| Phi-3-mini | 3.8B | ~2.5 GB | ~3.5 GB | Very good |
| Llama 3.1-8B | 8B | ~5.5 GB | ~6.5 GB | Excellent ❌ won't fit |

**Why Qwen2.5-1.5B?**
Balanced tradeoff between quality and RAM. 1.5B parameters is sufficient for the structured task of form understanding (classifying form type + extracting fields from clean OCR text).

Phi-3-mini would be more accurate but uses 2x the RAM. In the challenge scoring formula (accuracy/efficiency), the 1.5B model scores higher because its efficiency gain outweighs its accuracy loss.

**Disabled by default**: The 1.5B model takes 45-85s per inference and hallucinates values on blank forms (e.g., "1990-01-01" for a blank date field). Keyword detection + template fallback is faster (<10ms), deterministic, and more reliable for known form types. The LLM is kept as an optional enhancement (`use_llm=True`) for ambiguous cases.

**Why llama.cpp?**
llama.cpp is the most mature CPU-inference engine for quantized LLMs. It uses memory-mapped model files (mmap) to keep the model on disk until needed, supports Q4_K_M quantization (optimal quality/size tradeoff), and has stable Python bindings (llama-cpp-python).

```
Inference parameters:
- Temperature: 0.1 (deterministic for extraction)
- top_p: 0.9
- max_tokens: 512 (field extraction), 128 (form type)
- context length: 2048
- batch size: 512
```

**Prompt format** (shortened for 1.5B model):
- System prompt: Kenyan government clerk persona (English + Swahili)
- Form type: 5 one-line examples + JSON format instruction
- Field extraction: OCR text + known labels + "return JSON array only"
- JSON parsing: robust against markdown fences, leading/trailing text

---

## Vector Store

**Chosen**: FAISS (in-memory) — **not yet implemented**
**Alternative**: ChromaDB, SQLite, None

FAISS is planned for form template similarity matching — when a form doesn't match any known template exactly, we find the closest match via embedding similarity. The all-MiniLM-L6-v2 sentence transformer download was interrupted (timeout) and this feature is deferred to Week 3.

```
Index: FlatL2 (brute-force cosine similarity)
Dimension: 384 (all-MiniLM-L6-v2 embeddings)
Size: ~150 MB for template storage
```

---

## UI Framework

**Chosen**: Streamlit — **not yet built**
**Alternative**: React + FastAPI, Gradio, Tkinter

| Feature | Streamlit | React + FastAPI | Gradio | Tkinter |
|---|---|---|---|---|
| Single process | ✅ | ❌ (2 processes) | ✅ | ✅ |
| RAM overhead | ~100MB | ~400MB (2 runtimes) | ~200MB | ~50MB |
| Development speed | Fast | Slow | Fast | Slow |
| Visual polish | Good | Excellent | Good | Poor |
| Offline packaging | pip | Docker needed | pip | Built-in |

Streamlit wins for a hackathon: single Python process, no build step, no Docker. The trade-off is less visual flexibility, but for a demo that judges need to run, "it just works" is more important than pixel perfection.

---

## PDF Export

**Chosen**: ReportLab + PyMuPDF (fitz) — **not yet built**
**Alternative**: pdfkit, FPDF, pdf-lib (JS)

ReportLab generates PDFs from scratch (for filled digital copies). PyMuPDF reads and overlays text onto existing PDF forms. Together they cover all export cases.

```
Workflow:
1. PyMuPDF reads original form PDF → gets page dimensions
2. Coordinates from layout detection map to PDF coordinates
3. ReportLab/PyMuPDF overlays extracted text at correct positions
4. Output: filled_form.pdf
```

---

## Swahili Language Support

**How it works** (no separate translation model needed):

1. **Field labels**: Inline translations in `FieldSchema` — each field has `label_en` and `label_sw`
2. **LLM output**: System prompt tells Qwen2.5 to output field labels in the user's selected language. Qwen2.5's training data includes Swahili.
3. **OCR**: Tesseract configured with `-l eng` (the standard distribution lacks Swahili .traineddata, but Swahili uses Latin script, so the English model handles it)
4. **UI text**: Planned `src/ui/strings.py` — all UI strings stored in English + Swahili, toggled by session state (Week 3)

This avoids adding a translation model (extra RAM) while still delivering a functional bilingual experience.

---

## Dependency Summary

```
Core:
├── opencv-python-headless == 4.9.*   # Image preprocessing
├── pytesseract == 0.3.*              # Typed OCR
├── torch == 2.2.*                    # TrOCR inference (CPU)
├── transformers == 4.40.*            # TrOCR model loading
├── sentencepiece == 0.2.*            # Tokenizer (TrOCR)
├── protobuf == 5.26.*                # Serialization (TrOCR)
├── llama-cpp-python == 0.2.*         # LLM inference
├── streamlit == 1.35.*               # UI (Week 3)
├── faiss-cpu == 1.8.*                # Template similarity (Week 3)
├── sentence-transformers == 2.7.*    # Embeddings (Week 3)
├── PyMuPDF == 1.24.*                 # PDF read/manipulate (Week 3)
├── reportlab == 4.1.*                # PDF generation (Week 3)
├── Pillow == 10.3.*                  # Image handling
├── numpy == 1.26.*                   # Numerical ops
└── pydantic == 2.7.*                 # Data validation

System:
└── tesseract-ocr >= 5.0              # OCR engine
```

Total `pip install` size: ~2.5GB (includes torch CPU, which is the heaviest dependency at ~1.2GB).

---

## Memory Profile by Pipeline Mode

| Mode | Components | Total RAM | Status |
|---|---|---|---|
| **Fast path** | OpenCV + Tesseract + keyword detection | ~500MB | ✅ Default |
| + TrOCR | + PyTorch + TrOCR model | ~2GB | ⚠️ ~70s on CPU |
| + LLM | + Qwen2.5 GGUF (mmapped) | ~3GB | ⚠️ ~45-85s inference |
| **Full** | All of the above | ~5.5-6.5GB | ⚠️ Risk of swap |

---

## Why Not...

### Why not use a larger model and rely on swap?
Swap memory on an 8GB laptop means hitting disk. A single inference would take 30+ seconds. The challenge scores on speed and memory — swap disqualifies you.

### Why not use ONNX Runtime?
ONNX is faster for inference but adds complexity to model conversion. llama.cpp directly consumes popular GGUF models without conversion. For a 4-week build, simplicity wins.

### Why not Docker?
Docker adds ~1GB overhead and requires root or docker group membership. A clean `pip install` + system install of Tesseract is simpler for judges to run on their own machines.

### Why not a multilingual model instead of separate Swahili support?
Qwen2.5 already handles Swahili. The planned language strings file is only for UI labels — the LLM handles content-level translation.

### Why is form type detection keyword-based instead of LLM?
Keyword matching achieves 100% accuracy in <10ms with zero model overhead. The 1.5B LLM takes 45-85s and fails to follow JSON-only formatting instructions. For deterministic structured tasks on known government form patterns, keyword matching is superior in every dimension.

### Why are TrOCR and LLM disabled by default?
TrOCR takes ~70s for 14 field regions and produces garbage on blank forms. The LLM hallucinates values on blank forms. The fast path (Tesseract + keywords + templates) completes in 11.4s with deterministic, correct output. Users explicitly enable AI models when processing filled forms.
