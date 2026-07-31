"""Regression tests for Week 3 UI helpers.

Covers the editable-field rebuild (with verified checkbox state) and the
preview/regions-overlay image helpers. Pure helpers only — the Streamlit
fragments themselves need a running runtime.
"""

from __future__ import annotations

import numpy as np

from src.forms.fields import ExtractedField
from src.ocr.preprocess import BoundingBox
from src.ui.components import _load_preview_bytes, _rebuild_fields, _render_regions_overlay


def _make_field(
    key: str = "surname",
    value: str = "Ochieng",
    validated: bool = False,
    region_id: int = 3,
) -> ExtractedField:
    return ExtractedField(
        key=key,
        label_en="Surname",
        label_sw="Jina la Familia",
        value=value,
        confidence=0.85,
        is_handwritten=True,
        validated=validated,
        region_id=region_id,
    )


# ── _rebuild_fields ───────────────────────────────────────────────────


def test_rebuild_fields_preserves_all_attributes():
    """dataclasses.replace must carry every attribute except value/validated."""
    fields = [_make_field()]
    edited = _rebuild_fields(fields, {0: "Odhiambo"}, {})

    assert edited[0].value == "Odhiambo"
    assert edited[0].region_id == 3, "region_id was dropped during rebuild"
    assert edited[0].confidence == 0.85, "confidence mutated during rebuild"
    assert edited[0].is_handwritten is True, "is_handwritten mutated during rebuild"
    assert edited[0].validated is False, "validated mutated without a toggle"


def test_rebuild_fields_applies_verified_toggle():
    """Verified checkboxes must toggle validated both ways."""
    fields = [_make_field(validated=False), _make_field(value="", validated=True)]

    toggled = _rebuild_fields(fields, {}, {0: True, 1: False})

    assert toggled[0].validated is True, "validated not set True"
    assert toggled[1].validated is False, "validated not cleared"


def test_rebuild_fields_keeps_value_without_edit():
    """Fields with no edit entry keep their original value."""
    fields = [_make_field(value="Ochieng")]
    rebuilt = _rebuild_fields(fields, {}, {})

    assert rebuilt[0].value == "Ochieng"


def test_rebuild_fields_combines_edit_and_toggle():
    """An edit and a verified toggle on the same field apply together."""
    fields = [_make_field(value="Ochieng", validated=False)]
    rebuilt = _rebuild_fields(fields, {0: "Odhiambo"}, {0: True})

    assert rebuilt[0].value == "Odhiambo"
    assert rebuilt[0].validated is True


# ── _render_regions_overlay ───────────────────────────────────────────


def test_render_regions_overlay_returns_png():
    """Overlay rendering must produce valid PNG bytes with region boxes."""
    preprocessed = np.zeros((200, 300), dtype=np.uint8)
    regions = [
        BoundingBox(x=10, y=10, w=40, h=20, region_type="label"),
        BoundingBox(x=10, y=50, w=60, h=30, region_type="field"),
        BoundingBox(x=10, y=90, w=40, h=20, region_type="signature"),
    ]

    png = _render_regions_overlay(preprocessed, regions)

    assert png.startswith(b"\x89PNG"), "output is not a PNG"


def test_render_regions_overlay_unknown_type():
    """Unrecognized region types fall back to the unknown color without crashing."""
    preprocessed = np.zeros((200, 300), dtype=np.uint8)
    regions = [BoundingBox(x=0, y=0, w=10, h=10, region_type="unknown")]

    png = _render_regions_overlay(preprocessed, regions)

    assert png.startswith(b"\x89PNG")


# ── _load_preview_bytes ───────────────────────────────────────────────


def test_load_preview_bytes_png(tmp_path):
    """A real image file must be encoded to preview PNG bytes."""
    import cv2

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    path = tmp_path / "form.png"
    cv2.imwrite(str(path), img)

    data = _load_preview_bytes(str(path))

    assert data is not None
    assert data.startswith(b"\x89PNG")


def test_load_preview_bytes_missing_path():
    """A nonexistent file must return None instead of raising."""
    assert _load_preview_bytes("/nonexistent/form.png") is None
