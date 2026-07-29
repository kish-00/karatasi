"""Karatasi OCR Pipeline.

Provides a unified interface for preprocessing, layout detection,
typed OCR (Tesseract), and handwriting OCR (TrOCR).
"""

from src.ocr.preprocess import (
    BoundingBox,
    LayoutResult,
    PreprocessResult,
    detect_layout,
    load_image,
    preprocess,
)
from src.ocr.typed import OCRResult, OCRSegment, ocr_image, ocr_region, ocr_regions
from src.ocr.handwriting import (
    HandwritingResult,
    is_loaded,
    recognize_batch,
    recognize_handwriting,
    unload_model,
)

__all__ = [
    # Preprocessing
    "preprocess",
    "load_image",
    "PreprocessResult",
    # Layout
    "detect_layout",
    "LayoutResult",
    "BoundingBox",
    # Typed OCR
    "ocr_image",
    "ocr_region",
    "ocr_regions",
    "OCRResult",
    "OCRSegment",
    # Handwriting OCR
    "recognize_handwriting",
    "recognize_batch",
    "HandwritingResult",
    "is_loaded",
    "unload_model",
]
