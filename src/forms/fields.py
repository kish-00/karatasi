"""Field extraction schemas, validation, and extraction logic.

Defines the data model for extracted form fields and provides
validation rules and extraction orchestration.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from src.llm.prompts import FormType, extract_fields_prompt

logger = logging.getLogger(__name__)

Language = Literal["English", "Swahili"]


class FieldType(str, Enum):
    TEXT = "text"
    DATE = "date"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    SIGNATURE = "signature"
    PHOTO = "photo"


ValidationRule = Literal["required", "id_number", "phone", "date", "email", "number"]


@dataclass(frozen=True, slots=True)
class FieldSchema:
    """Expected field definition for a form template."""

    key: str
    """Machine-readable field identifier (snake_case)."""
    label_en: str
    """English label."""
    label_sw: str
    """Swahili label."""
    field_type: FieldType = FieldType.TEXT
    validation: list[ValidationRule] = field(default_factory=list)
    required: bool = False


@dataclass(slots=True)
class ExtractedField:
    """Single extracted field value with metadata."""

    key: str
    """Machine-readable field identifier."""
    label_en: str
    """English label."""
    label_sw: str
    """Swahili label."""
    value: str
    """Extracted text value."""
    confidence: float
    """OCR + LLM combined confidence (0.0-1.0)."""
    field_type: FieldType = FieldType.TEXT
    is_handwritten: bool = False
    validated: bool = False
    region_id: int | None = None
    """Index into layout field_regions for PDF overlay positioning."""


# ── Validation ──────────────────────────────────────────────────────


def validate_field(value: str, rules: list[ValidationRule]) -> list[str]:
    """Validate a field value against rules.

    Args:
        value: Field value to validate.
        rules: Validation rules to apply.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []
    for rule in rules:
        if rule == "required" and not value.strip():
            errors.append("Field is required")
        elif rule == "id_number":
            if value.strip() and not re.match(r"^\d{6,8}$", value.strip()):
                errors.append("ID number must be 6-8 digits")
        elif rule == "phone":
            if value.strip() and not re.match(r"^0\d{9}$", value.strip()):
                errors.append("Phone must be 10 digits starting with 0")
        elif rule == "date":
            if value.strip() and not re.match(
                r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", value.strip()
            ):
                errors.append("Date format: DD/MM/YYYY")
        elif rule == "email":
            if value.strip() and "@" not in value:
                errors.append("Invalid email")
        elif rule == "number":
            if value.strip() and not re.match(r"^\d+$", value.strip()):
                errors.append("Must be numeric")
    return errors


# ── Templates (known field schemas) ─────────────────────────────────


_ID_APPLICATION_FIELDS: list[FieldSchema] = [
    FieldSchema("serial_no", "Serial No.", "Nambari ya Msururu", FieldType.TEXT),
    FieldSchema("surname", "Surname", "Jina la Familia", FieldType.TEXT, ["required"]),
    FieldSchema("first_name", "First Name", "Jina la Kwanza", FieldType.TEXT, ["required"]),
    FieldSchema("other_names", "Other Names", "Majina Mengine", FieldType.TEXT),
    FieldSchema("date_of_birth", "Date of Birth", "Tarehe ya Kuzaliwa", FieldType.DATE, ["date"]),
    FieldSchema("place_of_birth", "Place of Birth", "Mahali pa Kuzaliwa", FieldType.TEXT),
    FieldSchema("district_of_birth", "District of Birth", "Wilaya ya Kuzaliwa", FieldType.TEXT),
    FieldSchema("sex", "Sex", "Jinsia", FieldType.TEXT),
    FieldSchema("height", "Height", "Urefu", FieldType.TEXT),
    FieldSchema("occupation", "Occupation", "Kazi", FieldType.TEXT),
    FieldSchema("marital_status", "Marital Status", "Hali ya Ndoa", FieldType.TEXT),
    FieldSchema("residence", "Residence", "Makazi", FieldType.TEXT),
    FieldSchema("signature", "Signature", "Sahihi", FieldType.SIGNATURE, ["required"]),
    FieldSchema("photo", "Passport Photo", "Picha", FieldType.PHOTO),
]

_LAND_BOARD_FIELDS: list[FieldSchema] = [
    FieldSchema("applicant_name", "Applicant Name", "Jina la Mwombaji", FieldType.TEXT, ["required"]),
    FieldSchema("id_number", "ID Number", "Nambari ya Kitambulisho", FieldType.TEXT, ["id_number"]),
    FieldSchema("property_description", "Property Description", "Maelezo ya Ardhi", FieldType.TEXT, ["required"]),
    FieldSchema("property_location", "Location", "Mahali", FieldType.TEXT),
    FieldSchema("consent_type", "Type of Consent", "Aina ya Ridhaa", FieldType.TEXT),
    FieldSchema("consideration", "Consideration (KSh)", "Mali (KSh)", FieldType.NUMBER, ["number"]),
    FieldSchema("signature", "Signature", "Sahihi", FieldType.SIGNATURE, ["required"]),
    FieldSchema("date", "Date", "Tarehe", FieldType.DATE, ["date"]),
]

_BIRTH_LATE_REG_FIELDS: list[FieldSchema] = [
    FieldSchema("child_name", "Child's Name", "Jina la Mtoto", FieldType.TEXT, ["required"]),
    FieldSchema("date_of_birth", "Date of Birth", "Tarehe ya Kuzaliwa", FieldType.DATE, ["date", "required"]),
    FieldSchema("place_of_birth", "Place of Birth", "Mahali pa Kuzaliwa", FieldType.TEXT),
    FieldSchema("sex", "Sex", "Jinsia", FieldType.TEXT),
    FieldSchema("father_name", "Father's Name", "Jina la Baba", FieldType.TEXT),
    FieldSchema("mother_name", "Mother's Name", "Jina la Mama", FieldType.TEXT),
    FieldSchema("father_id", "Father's ID", "Nambari ya Baba", FieldType.TEXT, ["id_number"]),
    FieldSchema("mother_id", "Mother's ID", "Nambari ya Mama", FieldType.TEXT, ["id_number"]),
    FieldSchema("informant_name", "Informant Name", "Jina la Mtoa Habari", FieldType.TEXT, ["required"]),
    FieldSchema("signature", "Signature", "Sahihi", FieldType.SIGNATURE, ["required"]),
    FieldSchema("date_registered", "Date Registered", "Tarehe ya Usajili", FieldType.DATE, ["date"]),
]

_BIRTH_CERT_FIELDS: list[FieldSchema] = [
    FieldSchema("child_name", "Child's Name", "Jina la Mtoto", FieldType.TEXT, ["required"]),
    FieldSchema("date_of_birth", "Date of Birth", "Tarehe ya Kuzaliwa", FieldType.DATE, ["date", "required"]),
    FieldSchema("place_of_birth", "Place of Birth", "Mahali pa Kuzaliwa", FieldType.TEXT),
    FieldSchema("sex", "Sex", "Jinsia", FieldType.TEXT),
    FieldSchema("father_name", "Father's Name", "Jina la Baba", FieldType.TEXT),
    FieldSchema("mother_name", "Mother's Name", "Jina la Mama", FieldType.TEXT),
    FieldSchema("registration_number", "Registration No.", "Nambari ya Usajili", FieldType.TEXT),
]

_TEMPLATES: dict[FormType, list[FieldSchema]] = {
    FormType.ID_APPLICATION: _ID_APPLICATION_FIELDS,
    FormType.LAND_BOARD: _LAND_BOARD_FIELDS,
    FormType.BIRTH_LATE_REGISTRATION: _BIRTH_LATE_REG_FIELDS,
    FormType.BIRTH_CERTIFICATE: _BIRTH_CERT_FIELDS,
}


def get_template_fields(form_type: FormType) -> list[FieldSchema]:
    """Get the expected field schemas for a form type.

    Args:
        form_type: The detected form type.

    Returns:
        List of FieldSchema for that form type (empty if unknown).
    """
    return _TEMPLATES.get(form_type, [])


# ── Field Extraction ────────────────────────────────────────────────


def extract_fields(
    ocr_text: str,
    form_type: FormType,
    *,
    use_llm: bool = True,
    language: Language = "English",
) -> list[ExtractedField]:
    """Extract structured fields from OCR text.

    Uses the LLM for primary extraction, with template-based defaults
    as a fallback for fields the LLM might miss.

    Args:
        ocr_text: Full OCR text output.
        form_type: Detected form type.
        use_llm: If True, use LLM for extraction.
        language: Output language.

    Returns:
        List of ExtractedField with values and confidence.
    """
    template_fields = get_template_fields(form_type)

    if not use_llm:
        return _template_fallback(template_fields, language)

    try:
        from src.llm.serve import get_server

        server = get_server()
        known_labels = [f.label_en for f in template_fields]

        prompt = extract_fields_prompt(
            ocr_text, form_type, language=language, known_labels=known_labels
        )
        result = server.infer(prompt, max_tokens=512, temperature=0.1)

        if result.text:
            parsed = _parse_json_array(result.text)
            if parsed:
                return _merge_llm_with_template(parsed, template_fields, language)
    except Exception:
        logger.exception("LLM field extraction failed")

    return _template_fallback(template_fields, language)


# ── Helpers ─────────────────────────────────────────────────────────


def _parse_json_array(text: str) -> list[dict] | None:
    """Find and parse a JSON array anywhere in LLM output text.

    Handles markdown fences, inline text before/after the array,
    and partial/invalid JSON gracefully.
    """
    text = text.strip()
    # Remove markdown fences (both ```json and ```)
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    json_str = text[start : end + 1]
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        return None


def _merge_llm_with_template(
    llm_fields: list[dict],
    template: list[FieldSchema],
    language: Language,
) -> list[ExtractedField]:
    """Merge LLM extraction results with template defaults.

    Template fields provide the canonical list. LLM results fill in values.
    """
    template_map = {f.key: f for f in template}
    llm_map: dict[str, ExtractedField] = {}

    for item in llm_fields:
        label = item.get("label", "")
        value = item.get("value", "")
        conf = float(item.get("confidence", 0.5))
        field_type = item.get("field_type", "text")
        label_sw = item.get("label_sw", label)

        # Try to match to a template key
        key = _label_to_key(label, template_map)
        if not key and template:
            key = f"field_{len(llm_map)}"
        elif not key:
            key = _label_to_snake_key(label, len(llm_map))

        try:
            ft = FieldType(field_type)
        except ValueError:
            ft = FieldType.TEXT
        # For inferred fields (no template), ensure label_sw has a visible fallback
        if not label_sw or label_sw == label:
            label_sw = f"{label} [inferred]"
        llm_map[key] = ExtractedField(
            key=key,
            label_en=label,
            label_sw=label_sw,
            value=value,
            confidence=conf,
            field_type=ft,
        )

    # Merge: template order, LLM values where available
    result: list[ExtractedField] = []
    used_keys = set()

    for schema in template:
        if schema.key in llm_map:
            ef = llm_map[schema.key]
            used_keys.add(schema.key)
        else:
            ef = ExtractedField(
                key=schema.key,
                label_en=schema.label_en,
                label_sw=schema.label_sw,
                value="",
                confidence=0.0,
                field_type=schema.field_type,
            )
        result.append(ef)

    # Add any LLM fields that didn't match a template key
    for key, ef in llm_map.items():
        if key not in used_keys:
            result.append(ef)

    return result


def _label_to_key(label: str, template_map: dict[str, FieldSchema]) -> str | None:
    """Match a label string to a template key using fuzzy matching."""
    label_lower = label.lower().strip()

    for key, schema in template_map.items():
        if label_lower == schema.label_en.lower():
            return key
        if label_lower == schema.label_sw.lower():
            return key
        if schema.label_en.lower() in label_lower:
            return key
        if schema.label_sw.lower() in label_lower:
            return key

    return None


_SNAKE_RE = re.compile(r"(?<=[a-z])[A-Z]|[^a-zA-Z0-9]+")


def _label_to_snake_key(label: str, fallback_idx: int) -> str:
    """Convert a human-readable label to a snake_case field key.

    Examples:
        "Full Name" → "full_name"
        "ID Number" → "id_number"
        "Date of Birth (DD/MM/YYYY)" → "date_of_birth"
    """
    clean = label.strip()
    if not clean:
        return f"field_{fallback_idx}"
    # Strip trailing parenthetical suffixes like (DD/MM/YYYY)
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", clean)
    # Strip apostrophes so "Father's Name" -> "Fathers Name" -> "fathers_name"
    clean = clean.replace("'", "").replace("\u2019", "")
    # Convert spaces/punctuation to underscores, lowercase
    snake = _SNAKE_RE.sub("_", clean).strip("_").lower()
    # Collapse consecutive underscores
    snake = re.sub(r"_+", "_", snake)
    # Guard against keys starting with a digit (not valid Python identifiers)
    if snake and snake[0].isdigit():
        snake = f"field_{snake}"
    return snake or f"field_{fallback_idx}"


def _template_fallback(
    template: list[FieldSchema], language: Language
) -> list[ExtractedField]:
    """Return template fields with empty values (fallback when LLM unavailable)."""
    return [
        ExtractedField(
            key=s.key,
            label_en=s.label_en,
            label_sw=s.label_sw,
            value="",
            confidence=0.0,
            field_type=s.field_type,
        )
        for s in template
    ]
