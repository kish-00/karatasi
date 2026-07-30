"""Unified processing pipeline: scan → structured data.

Wires OCR (preprocess + layout + Tesseract + TrOCR) with LLM
(form detection + field extraction) into a single end-to-end flow.
"""

from __future__ import annotations

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
from src.ocr.handwriting import recognize_handwriting
from src.ocr.preprocess import (
    BoundingBox,
    LayoutResult,
    PreprocessResult,
    detect_layout,
    is_web_portal,
    load_image,
    preprocess,
)
from src.ocr.typed import ocr_image, ocr_region

logger = logging.getLogger(__name__)

Language = Literal["English", "Swahili"]


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

    @property
    def mean_confidence(self) -> float:
        if not self.fields:
            return 0.0
        return sum(f.confidence for f in self.fields) / len(self.fields)


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

    # ── 1. Load + Preprocess ──
    img = load_image(str(image_path))
    proc = preprocess(img, original_dpi=original_dpi)

    # ── 2. Full-page Tesseract OCR ──
    ocr_result = ocr_image(proc.image)
    full_text = ocr_result.full_text

    # ── 3. Web-portal check ──
    if is_web_portal(full_text):
        elapsed = (time.perf_counter() - start) * 1000
        return PipelineResult(
            form_type=FormType.UNKNOWN,
            form_type_confidence=0.0,
            full_text=full_text,
            is_web_portal=True,
            elapsed_ms=elapsed,
        )

    # ── 4. Layout detection (preprocessed-space for OCR) ──
    layout = detect_layout(proc.image, proc.original_size, scale_to_original=False)

    # ── 5. Form type detection ──
    detection = detect_form_type(full_text, use_llm=use_llm, language=language)

    # ── 6. Field extraction ──
    fields = extract_fields(
        full_text, detection.form_type, use_llm=use_llm, language=language
    )

    # ── 7. Handwriting OCR on field regions (when explicitly enabled) ──
    hw_confidence = 0.0
    field_regions = [r for r in layout.regions if r.region_type == "field"]
    if use_trocr:
        hw_confidence = _run_handwriting_ocr(fields, field_regions, proc.image, full_text)

    for i, field in enumerate(fields):
        if i < len(field_regions):
            object.__setattr__(field, "region_id", i)

    elapsed = (time.perf_counter() - start) * 1000
    return PipelineResult(
        form_type=detection.form_type,
        form_type_confidence=detection.confidence,
        fields=fields,
        layout=layout,
        full_text=full_text,
        elapsed_ms=elapsed,
    )


def _run_handwriting_ocr(
    fields: list[ExtractedField],
    field_regions: list[BoundingBox],
    preprocessed: np.ndarray,
    full_text: str = "",
) -> float:
    """Run TrOCR on field regions and update field values.

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

    confidences: list[float] = []
    for i, field in enumerate(fields):
        if i >= len(field_regions):
            break
        if field.confidence >= 0.5:
            continue

        region = field_regions[i]
        h, w = preprocessed.shape[:2]
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

        try:
            hw = recognize_handwriting(crop, unload_after=False)
            if hw.text and hw.confidence > 0.6:
                # Skip if output matches printed text (form label, not handwriting)
                hw_words = set(hw.text.lower().split())
                overlap = hw_words & printed_tokens
                if overlap:
                    logger.debug(
                        "Skipping TrOCR on %s: matches printed text: %s",
                        field.key, hw.text[:40]
                    )
                    continue
                merged_conf = max(field.confidence, hw.confidence * 0.85)
                object.__setattr__(field, "value", hw.text)
                object.__setattr__(field, "confidence", merged_conf)
                object.__setattr__(field, "is_handwritten", True)
                confidences.append(hw.confidence)
        except Exception:
            logger.debug("Handwriting OCR failed on field %s", field.key)

    return float(np.mean(confidences)) if confidences else 0.0
