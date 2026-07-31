"""Unified processing pipeline: scan → structured data.

Wires OCR (preprocess + layout + Tesseract + TrOCR) with LLM
(form detection + field extraction) into a single end-to-end flow.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from src.forms.detector import detect_form_type
from src.forms.fields import ExtractedField, extract_fields
from src.llm.prompts import FormType
from src.ocr.handwriting import recognize_batch
from src.ocr.preprocess import (
    BoundingBox,
    LayoutResult,
    PreprocessResult,
    detect_layout,
    is_likely_form,
    is_web_portal,
    load_image,
    preprocess,
)
from src.ocr.typed import ocr_image

logger = logging.getLogger(__name__)

Language = Literal["English", "Swahili"]

# ── OCR result cache ─────────────────────────────────────────────────
# Caches full-page Tesseract output keyed by image content hash.
# This avoids re-running the ~11s Tesseract pass when the user
# changes the form type (re_extract_fields) on the same image.

_ocr_cache: dict[str, str] = {}
"""Maps content hash -> full_text, evicted on new uploads."""


def _image_content_hash(path: str) -> str:
    """Fast content hash for an image file (first 64KB + size)."""
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as f:
        chunk = f.read(65536)
        h.update(chunk)
    h.update(str(Path(path).stat().st_size).encode())
    return h.hexdigest()


def invalidate_ocr_cache() -> None:
    """Clear the OCR result cache (call when a new image is uploaded)."""
    _ocr_cache.clear()


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Complete pipeline output for a single form."""

    form_type: FormType
    form_type_confidence: float
    fields: list[ExtractedField] = field(default_factory=list)
    layout: LayoutResult | None = None
    full_text: str = ""
    is_web_portal: bool = False
    elapsed_ms: float = 0.0
    manual_override: bool = False
    """True if the form type was manually overridden by the user (vs auto-detected)."""
    page_count: int = 1
    """Number of pages processed (for multi-page PDFs)."""
    blur_warning: str = ""
    """Non-empty if the image appears blurry (low quality)."""
    rotate_warning: str = ""
    """Non-empty if the image was auto-rotated (was upside-down)."""
    non_form_warning: str = ""
    """Non-empty if the image may not be a government form."""
    preprocessed: np.ndarray | None = None
    """First-page preprocessed image (binarized) in region coordinate space.

    Used for the UI regions overlay and for embedding signature/photo
    crops in the PDF export. Held in memory only — never persisted.
    """

    @property
    def mean_confidence(self) -> float:
        if not self.fields:
            return 0.0
        return sum(f.confidence for f in self.fields) / len(self.fields)


def _pdf_page_count(path: str | Path) -> int:
    """Return the number of pages in a PDF (0 for non-PDF files)."""
    path = Path(path)
    if path.suffix.lower() not in {".pdf"}:
        return 0
    try:
        import fitz
        doc = fitz.open(str(path))
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return 0


def _process_single_page(
    img: np.ndarray,
    *,
    original_dpi: float = 200.0,
) -> tuple[PreprocessResult, str]:
    """Run preprocess + OCR on a single image page.

    Returns:
        (preprocess_result, full_text).
    """
    proc = preprocess(img, original_dpi=original_dpi)
    ocr_result = ocr_image(proc.image)
    return proc, ocr_result.full_text


def process_form(
    image_path: str | Path,
    *,
    language: Language = "English",
    use_llm: bool = False,
    use_trocr: bool = False,
    original_dpi: float = 200.0,
) -> PipelineResult:
    """Process a scanned form end-to-end.

    Args:
        image_path: Path to scanned form (PDF, JPG, PNG).
        language: Output language for labels.
        use_llm: If True, use LLM for field extraction.
        use_trocr: If True, run TrOCR handwriting recognition on field regions.
        original_dpi: Estimated DPI of the input.

    Returns:
        PipelineResult with detected form type and extracted fields.
    """
    start = time.perf_counter()

    # ── 1. Detect page count; load + preprocess + OCR each page ──
    page_count = _pdf_page_count(image_path)
    if page_count > 1:
        # Multi-page PDF: iterate all pages, combine OCR text
        import fitz
        doc = fitz.open(str(image_path))
        all_texts: list[str] = []
        first_proc: PreprocessResult | None = None
        page_imgs: list[np.ndarray] = []
        for page_idx in range(page_count):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=200)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, 3
            )
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            proc, text = _process_single_page(img_bgr, original_dpi=original_dpi)
            all_texts.append(text)
            page_imgs.append(img_bgr)
            if first_proc is None:
                first_proc = proc
        doc.close()
        full_text = "\n\n--- Page Break ---\n\n".join(all_texts)
        proc = first_proc
        img = page_imgs[0]
        page_count = page_count
    else:
        # Single image or single-page PDF
        img = load_image(str(image_path))
        proc, full_text = _process_single_page(img, original_dpi=original_dpi)
        page_count = 1

    # ── 2. Web-portal check ──
    if is_web_portal(full_text):
        elapsed = (time.perf_counter() - start) * 1000
        return PipelineResult(
            form_type=FormType.UNKNOWN,
            form_type_confidence=0.0,
            full_text=full_text,
            is_web_portal=True,
            elapsed_ms=elapsed,
            page_count=page_count,
        )

    # ── 3. Quality warnings (from first page) ──
    blur_warning = ""
    rotate_warning = ""
    if proc.blur_score < 50:
        blur_warning = f"Image appears blurry (score: {proc.blur_score:.0f}). OCR accuracy may be reduced."
    elif proc.blur_score < 100:
        blur_warning = f"Image may be slightly blurry (score: {proc.blur_score:.0f})."
    if proc.auto_rotated:
        rotate_warning = "Image was automatically rotated (was upside-down). Verify field positions."

    # ── 4. Layout detection (first page, preprocessed-space) ──
    layout = detect_layout(proc.image, proc.original_size, scale_to_original=False)

    # ── 5. Non-form check ──
    non_form_warning = ""
    is_form, non_form_reason = is_likely_form(full_text, len(layout.regions))
    if not is_form:
        non_form_warning = non_form_reason

    # ── 6. Form type detection ──
    detection = detect_form_type(full_text, use_llm=use_llm, language=language)

    # ── 7. Field extraction ──
    fields = extract_fields(
        full_text, detection.form_type, use_llm=use_llm, language=language
    )

    # ── 8. Handwriting OCR on first-page field regions (when enabled) ──
    hw_confidence = 0.0
    field_regions = [r for r in layout.regions if r.region_type == "field"]
    if use_trocr:
        hw_confidence = _run_handwriting_ocr(fields, field_regions, proc.image, full_text)

    for i, field in enumerate(fields):
        if i < len(field_regions):
            field.region_id = i

    elapsed = (time.perf_counter() - start) * 1000
    return PipelineResult(
        form_type=detection.form_type,
        form_type_confidence=detection.confidence,
        fields=fields,
        layout=layout,
        full_text=full_text,
        elapsed_ms=elapsed,
        page_count=page_count,
        blur_warning=blur_warning,
        rotate_warning=rotate_warning,
        non_form_warning=non_form_warning,
        preprocessed=proc.image,
    )


def re_extract_fields(
    result: PipelineResult,
    new_form_type: FormType,
    *,
    language: Language = "English",
) -> PipelineResult:
    """Re-extract fields with a different form type, preserving layout.

    This is the single entry point for form-type overrides. It
    extracts fields for the new type, attaches region IDs from the
    original layout (so PDF overlay still works), and marks the
    result as manually overridden.

    Args:
        result: The current pipeline result (layout is preserved).
        new_form_type: The form type to re-extract with.
        language: Output language for labels.

    Returns:
        A new PipelineResult with re-extracted fields and manual_override=True.
    """
    new_fields = extract_fields(
        result.full_text, new_form_type, use_llm=True, language=language
    )

    # Attach region_ids from the original layout so PDF export works
    field_regions = [
        r
        for r in (result.layout.regions if result.layout else [])
        if r.region_type == "field"
    ]
    for i, field in enumerate(new_fields):
        if i < len(field_regions):
            field.region_id = i

    return dataclasses.replace(
        result,
        form_type=new_form_type,
        form_type_confidence=1.0,
        fields=new_fields,
        manual_override=True,
    )


def _run_handwriting_ocr(
    fields: list[ExtractedField],
    field_regions: list[BoundingBox],
    preprocessed: np.ndarray,
    full_text: str = "",
) -> float:
    """Run TrOCR on field regions and update field values.

    Uses batch inference (loads model once for all regions).
    Filters out TrOCR output that matches Tesseract-printed text
    (i.e., form labels read as handwriting).

    Returns:
        Average confidence of handwriting results.
    """
    if not field_regions:
        return 0.0

    # Build set of known printed-text tokens from Tesseract
    printed_tokens: set[str] = set()
    for word in full_text.lower().split():
        word = word.strip(".,;:!?\"'()[]{}")
        if len(word) > 1:
            printed_tokens.add(word)

    # Prepare crops for all fields that need TrOCR
    crop_indices: list[int] = []
    crops: list[np.ndarray] = []
    h, w = preprocessed.shape[:2]

    for i, field in enumerate(fields):
        if i >= len(field_regions):
            break
        if field.confidence >= 0.5:
            continue

        region = field_regions[i]
        x1 = max(0, region.x - 4)
        y1 = max(0, region.y - 4)
        x2 = min(w, region.x + region.w + 4)
        y2 = min(h, region.y + region.h + 4)

        if x2 <= x1 or y2 <= y1:
            continue

        crop = preprocessed[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        # Skip nearly blank regions (no handwriting present)
        ink_ratio = float(np.sum(crop < 200)) / crop.size
        if ink_ratio < 0.01:
            continue

        crop_indices.append(i)
        crops.append(crop)

    if not crops:
        return 0.0

    # Run batch inference (loads model once, unloads after)
    try:
        batch_results = recognize_batch(crops, unload_after=True)
    except Exception:
        logger.exception("Batch TrOCR inference failed")
        return 0.0

    confidences: list[float] = []
    for idx, hw in zip(crop_indices, batch_results):
        field = fields[idx]
        if hw.text and hw.confidence > 0.6:
            # Skip if output matches printed text (form label, not handwriting)
            hw_words = set(hw.text.lower().split())
            overlap = hw_words & printed_tokens
            if overlap:
                logger.debug(
                    "Skipping TrOCR on %s: matches printed text: %s",
                    field.key, hw.text[:40],
                )
                continue
            merged_conf = max(field.confidence, hw.confidence * 0.85)
            field.value = hw.text
            field.confidence = merged_conf
            field.is_handwritten = True
            confidences.append(hw.confidence)

    return float(np.mean(confidences)) if confidences else 0.0
