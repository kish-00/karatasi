"""PDF export via PyMuPDF overlay on the original scanned form.

Overlays extracted field text onto the original form image/PDF
at the positions detected by layout analysis.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
import fitz

from src.pipeline import PipelineResult

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_OVERLAY_COLOR = (0, 0, 0.6)  # Dark blue — visible against originals
_FONT_SIZE_MIN = 8
_FONT_SIZE_MAX = 14
_PADDING = 2  # px inside field bounding box


def export_pdf(
    result: PipelineResult,
    original_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Overlay extracted fields onto the original form and save to output_path.

    Args:
        result: Pipeline output with fields and layout.
        original_path: Path to the original uploaded form (PDF, JPG, PNG).
        output_path: Where to write the filled PDF.

    Returns:
        The output path.
    """
    original_path = Path(original_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = original_path.suffix.lower()

    if suffix in (".pdf",):
        _overlay_pdf(result, original_path, output_path)
    else:
        _overlay_image(result, original_path, output_path)

    logger.info("PDF exported to %s", output_path)
    return output_path


def pdf_bytes(result: PipelineResult, original_path: str | Path) -> bytes:
    """Return filled PDF as bytes (for Streamlit download button)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        export_pdf(result, original_path, tmp_path)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Internal helpers ─────────────────────────────────────────────────


def _overlay_pdf(
    result: PipelineResult,
    original_path: Path,
    output_path: Path,
) -> None:
    """Overlay fields onto each page of a PDF form.

    Layout regions are from the first page only; overlay is applied
    to page 0 where coordinates match. Other pages are preserved
    unmodified in the output.
    """
    doc = fitz.open(str(original_path))

    for page_num in range(doc.page_count):
        page = doc[page_num]
        # Apply overlays only to the first page where layout data exists
        if page_num == 0:
            _apply_overlays(page, result, page.rect.width, page.rect.height)
        # Remaining pages pass through unmodified

    doc.save(str(output_path))
    doc.close()


def _overlay_image(
    result: PipelineResult,
    original_path: Path,
    output_path: Path,
) -> None:
    """Embed an image (JPG/PNG) in a new PDF page and overlay fields."""
    doc = fitz.open()

    # Determine image dimensions to size the page
    img = fitz.Pixmap(str(original_path))
    page_rect = fitz.Rect(0, 0, img.width, img.height)
    page = doc.new_page(width=img.width, height=img.height)

    # Insert the image
    page.insert_image(page_rect, filename=str(original_path))

    _apply_overlays(page, result, img.width, img.height)

    doc.save(str(output_path))
    doc.close()


def _apply_overlays(
    page: fitz.Page,
    result: PipelineResult,
    page_width: float,
    page_height: float,
) -> None:
    """Apply text overlays for every extracted field onto a page.

    Maps layout region coordinates (from preprocessed image space)
    to PDF page coordinates.

    Args:
        page: The PDF page to draw on.
        result: Pipeline result with fields and layout.
        page_width: Width of the PDF page in points.
        page_height: Height of the PDF page in points.
    """
    if not result.layout or not result.layout.regions:
        logger.warning("No layout regions available — cannot overlay fields")
        return

    # Compute scale from preprocessed image dimensions to PDF page
    preprocessed_shape = result.layout.original_shape  # (h, w) of original image
    if preprocessed_shape:
        scale_x = page_width / preprocessed_shape[1]
        scale_y = page_height / preprocessed_shape[0]
    else:
        scale_x = scale_y = 1.0

    # Get field regions (field-type regions from layout detection)
    field_regions = [r for r in result.layout.regions if r.region_type == "field"]

    for field in result.fields:
        if not field.value.strip() or field.confidence < 0.01:
            continue  # Skip empty or zero-confidence fields

        if field.region_id is None or field.region_id >= len(field_regions):
            logger.debug("No layout region for field %s (region_id=%s)", field.key, field.region_id)
            continue

        region = field_regions[field.region_id]

        # Scale region to PDF coordinates
        x0 = region.x * scale_x
        y0 = region.y * scale_y
        x1 = (region.x + region.w) * scale_x
        y1 = (region.y + region.h) * scale_y

        field_rect = fitz.Rect(x0 + _PADDING, y0 + _PADDING,
                               x1 - _PADDING, y1 - _PADDING)

        if field_rect.is_empty or field_rect.width < 1 or field_rect.height < 1:
            continue

        # Choose font size based on available height
        font_size = min(_FONT_SIZE_MAX, field_rect.height * 0.7)
        font_size = max(_FONT_SIZE_MIN, font_size)

        try:
            font = fitz.Font("helv")
        except Exception:
            font = None

        _draw_text(page, field_rect, field.value, font_size, font)


def _draw_text(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    font_size: float,
    font: fitz.Font | None,
) -> None:
    """Draw text inside a rectangle with clipping.

    If the text is wider than the rectangle, reduce font size iteratively.
    """
    # Try reducing font size until text fits
    for attempt in range(3):
        text_width = _text_width(text, font_size, font)
        if text_width <= rect.width or font_size <= _FONT_SIZE_MIN:
            break
        font_size = max(_FONT_SIZE_MIN, font_size - 2)

    try:
        page.insert_text(
            point=(rect.x0, rect.y0 + font_size),
            text=text,
            fontname="helv" if font is None else None,
            fontfile=None,
            fontsize=font_size,
            color=_OVERLAY_COLOR,
        )
    except Exception:
        logger.exception("Failed to overlay text: %s", text[:30])


def _text_width(text: str, font_size: float, font: fitz.Font | None) -> float:
    """Estimate the width of text at a given font size."""
    try:
        if font:
            w = font.text_length(text, fontsize=font_size)
        else:
            w = len(text) * font_size * 0.5  # rough estimate
        return w
    except Exception:
        return len(text) * font_size * 0.5
