"""Image preprocessing pipeline for document OCR.

Transforms raw scanned images into clean, normalized inputs ready for
Tesseract (typed text) and TrOCR (handwriting) recognition.

Pipeline steps:
1. Grayscale conversion
2. Adaptive thresholding (binarization)
3. Deskew (rotation correction)
4. Denoise (Gaussian blur + morphological ops)
5. DPI normalization (scale to 300 DPI)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from numpy.typing import NDArray

# ── Types ───────────────────────────────────────────────────────────

ImageArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class PreprocessResult:
    """Result of the preprocessing pipeline."""

    image: ImageArray
    """Processed image ready for OCR."""
    original_size: tuple[int, int]
    """(width, height) of original image."""
    deskew_angle: float
    """Rotation angle corrected in degrees."""
    elapsed_ms: float
    """Total preprocessing time in milliseconds."""


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A detected region on the form."""

    x: int
    y: int
    w: int
    h: int
    region_type: Literal["label", "field", "checkbox", "signature", "photo", "unknown"]
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class LayoutResult:
    """Result of layout detection."""

    regions: list[BoundingBox] = field(default_factory=list)
    label_field_pairs: list[tuple[BoundingBox, BoundingBox]] = field(default_factory=list)
    elapsed_ms: float = 0.0
    original_shape: tuple[int, int] = (0, 0)
    """(height, width) of the preprocessed image (region coordinate space)."""


# ── Constants ───────────────────────────────────────────────────────

TARGET_DPI = 300.0
"""Target resolution for OCR-ready images."""

MAX_IMAGE_DIMENSION = 4000
"""Maximum pixel dimension to avoid OOM on large scans."""


# ── Preprocessing Steps ─────────────────────────────────────────────


def _to_grayscale(image: ImageArray) -> ImageArray:
    """Convert BGR or RGBA image to grayscale."""
    if len(image.shape) == 2:
        return image
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def _adaptive_threshold(image: ImageArray) -> ImageArray:
    """Binarize using adaptive thresholding for varied lighting.

    Uses Gaussian adaptive threshold which handles uneven illumination
    common in phone-captured form photos.
    """
    return cv2.adaptiveThreshold(
        image,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )


def _deskew(image: ImageArray) -> tuple[ImageArray, float]:
    """Correct rotation skew using minAreaRect on text contours.

    Finds all text-like contours, computes the dominant angle via the
    minimum area rectangle, and rotates the image to compensate.

    Returns:
        Tuple of (corrected image, angle corrected in degrees).
    """
    # Invert so text is white on black (contours find white objects)
    inverted = cv2.bitwise_not(image)

    # Find all non-zero pixels
    coords = cv2.findNonZero(inverted)
    if coords is None or len(coords) < 100:
        return image, 0.0

    # Compute min area rect to get skew angle
    rect = cv2.minAreaRect(coords)
    angle = rect[2]

    # Normalize angle: minAreaRect returns in [-90, 0)
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    # Skip if angle is negligibly small
    if abs(angle) < 0.5:
        return image, 0.0

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    # Compute new bounding dimensions to avoid cropping
    cos_abs = abs(rotation_matrix[0, 0])
    sin_abs = abs(rotation_matrix[0, 1])
    new_w = int(h * sin_abs + w * cos_abs)
    new_h = int(h * cos_abs + w * sin_abs)

    # Adjust translation to center the image
    rotation_matrix[0, 2] += new_w / 2 - center[0]
    rotation_matrix[1, 2] += new_h / 2 - center[1]

    corrected = cv2.warpAffine(
        image,
        rotation_matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return corrected, angle


def _denoise(image: ImageArray) -> ImageArray:
    """Apply denoising to remove scan noise and specks.

    Uses a light Gaussian blur followed by morphological closing
    to fill small gaps in broken text.
    """
    # Light blur to smooth noise
    blurred = cv2.GaussianBlur(image, (3, 3), 0)

    # Morphological closing to close broken text gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)

    return cleaned


def _scale_to_dpi(image: ImageArray, original_dpi: float = 200.0) -> ImageArray:
    """Scale image to target DPI.

    Args:
        image: Input image.
        original_dpi: Estimated DPI of the input (default 200 for phone photos).

    Returns:
        Scaled image at TARGET_DPI.
    """
    if original_dpi <= 0:
        return image

    scale = TARGET_DPI / original_dpi

    # Clamp to avoid excessive upscaling of very low-DPI images
    scale = max(0.5, min(scale, 3.0))

    if abs(scale - 1.0) < 0.01:
        return image

    h, w = image.shape[:2]
    new_dim = (int(w * scale), int(h * scale))
    return cv2.resize(image, new_dim, interpolation=cv2.INTER_CUBIC)


def _resize_if_needed(image: ImageArray) -> ImageArray:
    """Downscale if image exceeds maximum dimension to prevent OOM."""
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim <= MAX_IMAGE_DIMENSION:
        return image

    scale = MAX_IMAGE_DIMENSION / max_dim
    new_dim = (int(w * scale), int(h * scale))
    return cv2.resize(image, new_dim, interpolation=cv2.INTER_AREA)


# ── Public API ──────────────────────────────────────────────────────


def preprocess(
    image: ImageArray,
    *,
    original_dpi: float = 200.0,
) -> PreprocessResult:
    """Run the full preprocessing pipeline on a scanned document image.

    Steps: grayscale → resize → threshold → deskew → denoise → DPI scale.

    Args:
        image: Input image (BGR or grayscale).
        original_dpi: Estimated DPI of the input (default 200).

    Returns:
        PreprocessResult with processed image and metadata.
    """
    start = time.perf_counter()
    original_size = (image.shape[1], image.shape[0])

    # 1. Grayscale
    gray = _to_grayscale(image)

    # 2. Downscale if needed (before expensive ops)
    gray = _resize_if_needed(gray)

    # 3. Adaptive threshold
    binary = _adaptive_threshold(gray)

    # 4. Deskew
    deskewed, angle = _deskew(binary)

    # 5. Denoise
    cleaned = _denoise(deskewed)

    # 6. DPI normalization
    result = _scale_to_dpi(cleaned, original_dpi)

    elapsed = (time.perf_counter() - start) * 1000
    return PreprocessResult(
        image=result,
        original_size=original_size,
        deskew_angle=angle,
        elapsed_ms=elapsed,
    )


WEB_PORTAL_PATTERNS = [
    "enable javascript",
    "enable cookies",
    "javascript and cookies",
]
"""Text patterns that indicate a PDF is a web-portal page, not a scanned form."""


def is_web_portal(text: str) -> bool:
    """Check if OCR text indicates the PDF is a web-portal/interstitial page.

    Web portals often serve PDFs that require JavaScript to render,
    resulting in "Enable JavaScript and cookies to continue" being the
    only OCR-extractable content.

    Returns:
        True if the text matches known web-portal patterns.
    """
    text_lower = text.lower()
    for pattern in WEB_PORTAL_PATTERNS:
        if pattern in text_lower:
            return True
    return False


def load_image(path: str | Path) -> ImageArray:
    """Load an image from disk.

    Supports PNG, JPG, TIFF, and PDF (via PyMuPDF fallback).

    Args:
        path: Path to image file.

    Returns:
        Image as a numpy array (BGR format for OpenCV).
    """
    path = Path(path)
    if not path.exists():
        msg = f"Image not found: {path}"
        raise FileNotFoundError(msg)

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is not None:
        return image

    # Fallback: try PyMuPDF for PDFs
    if path.suffix.lower() in {".pdf"}:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        page = doc[0]
        pix = page.get_pixmap(dpi=int(TARGET_DPI))
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        doc.close()
        return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    msg = f"Could not load image: {path}"
    raise ValueError(msg)


# ── Layout Detection ────────────────────────────────────────────────


def _classify_region(
    w: int,
    h: int,
    area: int,
    image_h: int,
    image_w: int,
    x: int,
    y: int,
) -> Literal["label", "field", "checkbox", "signature", "photo", "unknown"]:
    """Classify a detected contour region by its geometry and position.

    Heuristics based on typical Kenyan government form layouts:
    - Checkbox: small square (aspect ratio ~1:1)
    - Signature: wide region near bottom
    - Photo: large rectangle in upper section
    - Label: small text region, typically upper-left area
    - Field: rectangular area adjacent to labels
    """
    aspect = w / h if h > 0 else 0
    area_ratio = area / (image_h * image_w)

    # Checkbox: small square
    if area_ratio < 0.005 and 0.7 < aspect < 1.5 and w < 60 and h < 60:
        return "checkbox"

    # Signature: wide region near bottom third
    if y > image_h * 0.65 and aspect > 3.0 and area_ratio > 0.01:
        return "signature"

    # Photo: large rectangle, typically upper half
    if area_ratio > 0.05 and 0.6 < aspect < 1.5 and y < image_h * 0.5:
        return "photo"

    # Field: medium-sized region with horizontal aspect
    if 0.005 < area_ratio < 0.05 and aspect > 1.5:
        return "field"

    # Label: small region, left side of form, must be large enough to read
    if area_ratio < 0.01 and x < image_w * 0.5 and w >= 30 and h >= 15:
        return "label"

    return "unknown"


def detect_layout(
    preprocessed: ImageArray,
    original_shape: tuple[int, int],
    *,
    scale_to_original: bool = True,
) -> LayoutResult:
    """Detect and classify regions in a preprocessed form image.

    Strategy:
    1. Find text-sized connected components (small contours)
    2. Merge nearby components into text regions using morphological dilation
    3. Classify each merged region by geometry and position
    4. Pair labels with adjacent fields

    Args:
        preprocessed: Preprocessed binary image.
        original_shape: (width, height) of the original image.
        scale_to_original: If True, region coords are mapped back to
            original image space (for display/overlays). If False,
            coords stay in preprocessed image space (for OCR cropping).

    Returns:
        LayoutResult with classified regions and label-field pairs.
    """
    start = time.perf_counter()
    orig_w, orig_h = original_shape
    curr_h, curr_w = preprocessed.shape[:2]
    scale_x = orig_w / curr_w
    scale_y = orig_h / curr_h

    # ── Step 1: Find text-sized connected components ──
    # Invert so text is white on black
    inverted = cv2.bitwise_not(preprocessed)

    # Find all small contours (text characters, words)
    all_contours, _ = cv2.findContours(
        inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # ── Step 2: Merge nearby components into regions ──
    # Draw all text-sized contours onto a blank mask, then dilate to merge
    total_area = curr_h * curr_w
    mask = np.zeros((curr_h, curr_w), dtype=np.uint8)

    for cnt in all_contours:
        area = cv2.contourArea(cnt)
        if area < 20 or area > total_area * 0.4:  # Skip noise and page boundary
            continue
        cv2.drawContours(mask, [cnt], -1, 255, thickness=-1)

    # Dilate to merge nearby text into region blocks
    merge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    merged = cv2.dilate(mask, merge_kernel, iterations=2)

    # Find merged region contours
    region_contours, _ = cv2.findContours(
        merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # ── Step 3: Classify each region ──
    regions: list[BoundingBox] = []
    for cnt in region_contours:
        area = cv2.contourArea(cnt)
        if area < 100:  # Filter noise
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        region_type = _classify_region(w, h, int(area), curr_h, curr_w, x, y)

        if scale_to_original:
            # Scale coordinates back to original image space for display
            x_out, y_out = int(x * scale_x), int(y * scale_y)
            w_out, h_out = int(w * scale_x), int(h * scale_y)
        else:
            # Keep coordinates in preprocessed image space for OCR
            x_out, y_out, w_out, h_out = x, y, w, h

        regions.append(
            BoundingBox(
                x=x_out, y=y_out, w=w_out, h=h_out,
                region_type=region_type,
            )
        )

    # ── Step 4: Pair labels with fields ──
    labels = [r for r in regions if r.region_type == "label"]
    fields = [r for r in regions if r.region_type == "field"]

    pairs: list[tuple[BoundingBox, BoundingBox]] = []
    for label in sorted(labels, key=lambda r: r.y):
        best_field: BoundingBox | None = None
        best_dist = float("inf")

        for field in fields:
            dy = field.y - label.y
            dx = field.x - (label.x + label.w)
            if dy < -label.h:  # Field is above label — skip
                continue

            dist = math.sqrt(max(dx, 0) ** 2 + max(dy, 0) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_field = field

        if best_field is not None and best_dist < orig_w * 0.3:
            pairs.append((label, best_field))

    elapsed = (time.perf_counter() - start) * 1000
    return LayoutResult(
        regions=regions,
        label_field_pairs=pairs,
        elapsed_ms=elapsed,
        original_shape=(curr_h, curr_w),
    )
