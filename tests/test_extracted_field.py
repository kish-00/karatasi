"""Regression tests for ExtractedField data integrity.

These tests verify that field attributes survive editing operations
and that the dataclass contract is maintained — preventing the
class of bugs where fields like region_id are silently dropped
during field rebuild.
"""

from __future__ import annotations

import dataclasses

from src.forms.fields import ExtractedField, _label_to_snake_key
from src.llm.prompts import FormType
from src.pipeline import PipelineResult, re_extract_fields


# ── ExtractedField data integrity ──────────────────────────────────────


def test_edited_field_preserves_all_attributes():
    """dataclasses.replace must carry every attribute unchanged except 'value'."""
    original = ExtractedField(
        key="surname",
        label_en="Surname",
        label_sw="Jina la Familia",
        value="Ochieng",
        confidence=0.85,
        field_type="text",  # type: ignore[arg-type]
        is_handwritten=True,
        validated=False,
        region_id=3,
    )
    edited = dataclasses.replace(original, value="Odhiambo")

    assert edited.region_id == 3, "region_id was dropped during edit"
    assert edited.value == "Odhiambo", "new value not applied"
    assert edited.confidence == 0.85, "confidence mutated during edit"


def test_region_id_defaults_to_none():
    """Newly created fields without explicit region_id must default to None."""
    field = ExtractedField(
        key="test", label_en="Test", label_sw="Jaribio",
        value="", confidence=0.0,
    )
    assert field.region_id is None, "default region_id should be None"


def test_unfrozen_mutation():
    """ExtractedField is intentionally unfrozen — direct mutation must work."""
    field = ExtractedField(
        key="name", label_en="Name", label_sw="Jina",
        value="", confidence=0.0,
    )
    field.value = "Mutated"
    field.confidence = 0.95
    field.region_id = 1
    assert field.value == "Mutated"
    assert field.confidence == 0.95
    assert field.region_id == 1


# ── _label_to_snake_key ────────────────────────────────────────────────


def test_snake_key_basic_labels():
    """Standard labels produce clean snake_case keys."""
    assert _label_to_snake_key("Full Name", 0) == "full_name"
    assert _label_to_snake_key("ID Number", 1) == "id_number"


def test_snake_key_strips_parenthetical_suffix():
    """Parenthetical qualifiers like (DD/MM/YYYY) are stripped."""
    assert _label_to_snake_key("Date of Birth (DD/MM/YYYY)", 2) == "date_of_birth"


def test_snake_key_strips_apostrophes():
    """Apostrophes are removed so 'Father's Name' -> 'fathers_name'."""
    assert _label_to_snake_key("Father's Name", 3) == "fathers_name"


def test_snake_key_empty_or_whitespace():
    """Empty or whitespace-only labels produce a fallback key."""
    assert _label_to_snake_key("", 4) == "field_4"
    assert _label_to_snake_key("  ", 5) == "field_5"


def test_snake_key_digit_leading():
    """Labels starting with a digit get a field_ prefix so the key is a valid identifier."""
    assert _label_to_snake_key("3. Full Name", 6) == "field_3_full_name"


# ── PipelineResult manual_override ─────────────────────────────────────


def test_manual_override_defaults_to_false():
    """A freshly created PipelineResult must have manual_override=False."""
    result = PipelineResult(
        form_type=FormType.UNKNOWN,
        form_type_confidence=0.0,
        fields=[
            ExtractedField(key="test", label_en="Test", label_sw="Jaribio", value="x", confidence=0.5),
        ],
    )
    assert result.manual_override is False


def test_re_extract_fields_attaches_region_ids(tmp_path):
    """re_extract_fields must attach region_ids from the original layout on re-extracted fields."""
    from src.ocr.preprocess import BoundingBox, LayoutResult

    # Build a minimal PipelineResult with a layout containing 2 field regions
    fields = [
        ExtractedField(key="name", label_en="Name", label_sw="Jina", value="Alice", confidence=0.9),
    ]
    layout = LayoutResult(
        regions=[
            BoundingBox(x=10, y=10, w=100, h=30, region_type="field"),
            BoundingBox(x=10, y=50, w=100, h=30, region_type="field"),
        ],
        original_shape=(600, 800),
    )
    result = PipelineResult(
        form_type=FormType.UNKNOWN,
        form_type_confidence=0.0,
        fields=fields,
        layout=layout,
        full_text="Sample form text with Name field content",
    )

    # Re-extract with a known Kenyan form type
    new_result = re_extract_fields(result, FormType.ID_APPLICATION, language="English")

    assert isinstance(new_result, PipelineResult)
    assert new_result.form_type == FormType.ID_APPLICATION
    assert len(new_result.fields) > 0
    # First two fields should have region_id 0, 1 (tied to layout region indices)
    if len(new_result.fields) >= 2:
        assert new_result.fields[0].region_id == 0
        assert new_result.fields[1].region_id == 1
    # manual_override must be True
    assert new_result.manual_override is True
