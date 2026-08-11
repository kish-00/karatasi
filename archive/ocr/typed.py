"""Tesseract OCR wrapper for typed/printed text recognition.

Optimized for Kenyan government forms with Swahili language support.
Configuration tuned for document OCR rather than general scene text.

Key features:
- Optimized Tesseract config (PSM 6, OEM 3)
- Region-of-interest cropping from layout detection
- Per-segment confidence scoring
- Swahili + English language support
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from src.ocr.preprocess import BoundingBox

# ── Tesseract Binary Setup ──────────────────────────────────────
# Point pytesseract at our venv-bundled Tesseract binary.
_VENV_PREFIX = Path(__file__).resolve().parents[2] / "venv"
_TESSERACT_BIN = str(_VENV_PREFIX / "bin" / "tesseract")
_TESSDATA_DIR = str(_VENV_PREFIX / "share" / "tessdata")

# Set process environment so Tesseract's child process finds libraries
os.environ.setdefault("LD_LIBRARY_PATH",
    f"{_VENV_PREFIX}/lib/x86_64-linux-gnu:{os.environ.get('LD_LIBRARY_PATH', '')}")
os.environ.setdefault("TESSDATA_PREFIX", _TESSDATA_DIR)

ImageArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class OCRSegment:
    """A single recognized text segment."""

    text: str
    confidence: float
    bbox: BoundingBox | None = None


@dataclass(frozen=True, slots=True)
class OCRResult:
    """Result of typed OCR on an image or region."""

    segments: list[OCRSegment] = field(default_factory=list)
    full_text: str = ""
    elapsed_ms: float = 0.0

    @property
    def mean_confidence(self) -> float:
        if not self.segments:
            return 0.0
        return sum(s.confidence for s in self.segments) / len(self.segments)


# ── Tesseract Configuration ─────────────────────────────────────────

# PSM (Page Segmentation Mode) 6: Assume a single uniform block of text.
# This works well for cropped field regions and form labels.
# For full-page OCR, PSM 3 (automatic) is better for layout detection.
_PSM_FULL_PAGE = 3
_PSM_SINGLE_BLOCK = 6

# OEM (OCR Engine Mode) 3: Default, uses both LSTM + legacy.
_OEM = 3

# Languages: English only (swk .traineddata unavailable via standard repos).
# Swahili typed OCR is handled by the eng model since Swahili uses Latin script.
_LANGS = "eng"


def _build_config(
    psm: int = _PSM_SINGLE_BLOCK,
    lang: str = _LANGS,
    *,
    character_whitelist: str | None = None,
) -> str:
    """Build Tesseract config string.

    Args:
        psm: Page segmentation mode.
        lang: Language string for Tesseract.
        character_whitelist: Optional set of allowed characters.

    Returns:
        Config string for pytesseract.image_to_data().
    """
    config = [
        f"--psm {psm}",
        f"--oem {_OEM}",
        "-c",
        "textord_min_linesize=2.5",  # Smaller text detection
        "-c",
        "textord_noise_normiles=0.5",  # Aggressive noise normalization
    ]

    if character_whitelist:
        config.extend(["-c", f"tessedit_char_whitelist={character_whitelist}"])

    return " ".join(config)


# ── Public API ──────────────────────────────────────────────────────


def ensure_tesseract() -> bool:
    """Verify Tesseract is installed and accessible.

    Returns:
        True if Tesseract is available, False otherwise.
    """
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BIN
        pytesseract.get_tesseract_version()
        return True
    except (FileNotFoundError, OSError):
        return False


def ocr_image(
    image: ImageArray,
    *,
    lang: str = _LANGS,
    character_whitelist: str | None = None,
) -> OCRResult:
    """Run Tesseract OCR on a full image.

    Args:
        image: Preprocessed image (grayscale or binary works best).
        lang: Tesseract language string (default: eng+swk).
        character_whitelist: Optional character constraint.

    Returns:
        OCRResult with recognized text segments and confidence.
    """
    import pytesseract

    start = time.perf_counter()

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    config = _build_config(psm=_PSM_FULL_PAGE, lang=lang, character_whitelist=character_whitelist)

    # Use image_to_data for per-character confidence data
    data = pytesseract.image_to_data(gray, lang=lang, config=config, output_type=pytesseract.Output.DICT)

    segments: list[OCRSegment] = []
    text_parts: list[str] = []

    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        conf = float(data["conf"][i]) if data["conf"][i] != "-1" else 0.0

        if not text or conf < 10:
            continue

        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        bbox = BoundingBox(x=x, y=y, w=w, h=h, region_type="label", confidence=conf / 100.0)

        segments.append(
            OCRSegment(text=text, confidence=conf / 100.0, bbox=bbox)
        )
        text_parts.append(text)

    elapsed = (time.perf_counter() - start) * 1000
    return OCRResult(
        segments=segments,
        full_text=" ".join(text_parts),
        elapsed_ms=elapsed,
    )


def ocr_region(
    image: ImageArray,
    region: BoundingBox,
    *,
    lang: str = _LANGS,
    padding: int = 4,
) -> OCRResult:
    """Run Tesseract OCR on a specific region of the image.

    Crops the image to the region's bounding box (with padding) and runs
    OCR with automatic page segmentation.

    Args:
        image: Full preprocessed image.
        region: BoundingBox defining the region to OCR.
        lang: Tesseract language string.
        padding: Extra pixels added around the crop (helps when bounding
                 box cuts text edges).

    Returns:
        OCRResult for the cropped region.
    """
    h, w = image.shape[:2]

    x1 = max(0, region.x - padding)
    y1 = max(0, region.y - padding)
    x2 = min(w, region.x + region.w + padding)
    y2 = min(h, region.y + region.h + padding)

    if x2 <= x1 or y2 <= y1:
        return OCRResult()

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return OCRResult()

    return ocr_image(crop, lang=lang)


def ocr_regions(
    image: ImageArray,
    regions: Sequence[BoundingBox],
    *,
    lang: str = _LANGS,
) -> dict[int, OCRResult]:
    """Run Tesseract OCR on multiple regions.

    Each region is cropped and OCR'd independently with single-block PSM.

    Args:
        image: Full preprocessed image.
        regions: Bounding boxes to OCR.
        lang: Tesseract language string.

    Returns:
        Dict mapping region index to OCRResult.
    """
    return {i: ocr_region(image, region, lang=lang) for i, region in enumerate(regions)}


def available_languages() -> list[str]:
    """List languages available in the installed Tesseract.

    Returns:
        Sorted list of language codes (e.g. ['eng', 'swk']).
    """
    try:
        import pytesseract

        return sorted(pytesseract.get_languages())
    except (FileNotFoundError, OSError):
        return []
