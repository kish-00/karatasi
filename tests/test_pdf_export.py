"""Regression tests for Week 3 PDF export features.

Covers DejaVu Sans font resolution and signature/photo region crop
embedding in the exported PDF.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np

from src.export.pdf import _find_dejavu_font, export_pdf
from src.forms.fields import ExtractedField, FieldType
from src.llm.prompts import FormType
from src.ocr.preprocess import BoundingBox, LayoutResult
from src.pipeline import PipelineResult


def _make_result(
    preprocessed: np.ndarray,
    field_type: FieldType,
    value: str = "",
) -> PipelineResult:
    layout = LayoutResult(
        regions=[BoundingBox(x=50, y=50, w=40, h=40, region_type="field")],
        original_shape=preprocessed.shape[:2],
    )
    return PipelineResult(
        form_type=FormType.ID_APPLICATION,
        form_type_confidence=1.0,
        fields=[
            ExtractedField(
                key="signature",
                label_en="Signature",
                label_sw="Sahihi",
                value=value,
                confidence=0.9,
                field_type=field_type,
                region_id=0,
            )
        ],
        layout=layout,
        full_text="",
        preprocessed=preprocessed,
    )


def _write_blank_pdf(tmp_path: Path) -> Path:
    """Create a blank single-page PDF as the export original."""
    doc = fitz.open()
    doc.new_page(width=200, height=300)
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()
    return path


# ── DejaVu Sans ───────────────────────────────────────────────────────


def test_find_dejavu_font_exists():
    """DejaVu Sans must resolve to an existing font file on this machine."""
    font_path = _find_dejavu_font()

    assert font_path is not None, "DejaVu Sans not found"
    assert Path(font_path).is_file(), "resolved font path does not exist"


# ── Signature/photo crop embedding ────────────────────────────────────


def test_signature_region_embedded_as_image(tmp_path):
    """A signature region with ink must be embedded as an image in the export."""
    preprocessed = np.full((200, 300), 255, dtype=np.uint8)
    preprocessed[50:90, 50:90] = 30  # dark ink inside the field region
    result = _make_result(preprocessed, FieldType.SIGNATURE)

    out = tmp_path / "out.pdf"
    export_pdf(result, _write_blank_pdf(tmp_path), out)

    doc = fitz.open(str(out))
    try:
        assert len(doc[0].get_images(full=True)) > 0, "signature crop not embedded"
    finally:
        doc.close()


def test_blank_signature_region_not_embedded(tmp_path):
    """A blank (no-ink) signature region must not produce an image."""
    preprocessed = np.full((200, 300), 255, dtype=np.uint8)  # all white
    result = _make_result(preprocessed, FieldType.SIGNATURE)

    out = tmp_path / "out.pdf"
    export_pdf(result, _write_blank_pdf(tmp_path), out)

    doc = fitz.open(str(out))
    try:
        assert len(doc[0].get_images(full=True)) == 0, "blank crop was embedded"
    finally:
        doc.close()


def test_photo_region_embedded_as_image(tmp_path):
    """Photo fields follow the same crop-embedding path as signatures."""
    preprocessed = np.full((200, 300), 255, dtype=np.uint8)
    preprocessed[50:90, 50:90] = 40
    result = _make_result(preprocessed, FieldType.PHOTO)

    out = tmp_path / "out.pdf"
    export_pdf(result, _write_blank_pdf(tmp_path), out)

    doc = fitz.open(str(out))
    try:
        assert len(doc[0].get_images(full=True)) > 0, "photo crop not embedded"
    finally:
        doc.close()


def test_text_field_overlay_still_works(tmp_path):
    """Regular text fields must still be overlaid as text (not images)."""
    preprocessed = np.full((200, 300), 255, dtype=np.uint8)
    result = _make_result(preprocessed, FieldType.TEXT, value="Ochieng")

    out = tmp_path / "out.pdf"
    export_pdf(result, _write_blank_pdf(tmp_path), out)

    doc = fitz.open(str(out))
    try:
        assert "Ochieng" in doc[0].get_text(), "text overlay missing from export"
        assert len(doc[0].get_images(full=True)) == 0, "text field wrongly embedded as image"
    finally:
        doc.close()
