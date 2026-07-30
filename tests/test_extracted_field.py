"""Regression tests for ExtractedField data integrity.

These tests verify that field attributes survive editing operations
and that the dataclass contract is maintained — preventing the
class of bugs where fields like region_id are silently dropped
during field rebuild.
"""

from __future__ import annotations

import dataclasses

from src.forms.fields import ExtractedField, _label_to_snake_key


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


def test_label_to_snake_key():
    """_label_to_snake_key must produce clean snake_case keys from arbitrary labels."""
    assert _label_to_snake_key("Full Name", 0) == "full_name"
    assert _label_to_snake_key("ID Number", 1) == "id_number"
    assert _label_to_snake_key("Date of Birth (DD/MM/YYYY)", 2) == "date_of_birth"
    assert _label_to_snake_key("Father's Name", 3) == "father_s_name"
    assert _label_to_snake_key("", 4) == "field_4"
    assert _label_to_snake_key("  ", 5) == "field_5"
