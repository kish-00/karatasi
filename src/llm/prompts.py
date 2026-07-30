"""Prompt templates for form understanding.

Provides system prompts, form type detection prompts, and field extraction
prompts for the local LLM. All prompts follow a Kenyan government clerk
persona and support English + Swahili output.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal


class FormType(str, Enum):
    """Known Kenyan government form types."""

    ID_APPLICATION = "ID_APPLICATION"
    LAND_BOARD = "LAND_BOARD"
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"
    BIRTH_LATE_REGISTRATION = "BIRTH_LATE_REGISTRATION"
    BIRTH_REGISTRATION = "BIRTH_REGISTRATION"
    KRA_PIN = "KRA_PIN"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    UNKNOWN = "UNKNOWN"


Language = Literal["English", "Swahili"]


# ── System Prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Kenyan government clerk who reads both English and Swahili.
Your job is to understand scanned government forms and extract structured data from them.

Rules:
- Be precise and deterministic (output only what you see, never guess).
- If text is illegible or missing, mark confidence as low.
- Output field labels in the requested language.
- For Swahili: use standard Kenyan Swahili terms (e.g. "Jina Kamili" for "Full Name").
- Never fabricate data. Empty fields stay empty."""  # noqa: E501


# ── Form Type Detection ─────────────────────────────────────────────

FORM_TYPE_PROMPT_TEMPLATE = """{system}

Identify the Kenyan government form type from OCR text.

Valid form types: ID_APPLICATION, LAND_BOARD, BIRTH_CERTIFICATE, BIRTH_LATE_REGISTRATION, BIRTH_REGISTRATION, KRA_PIN, DRIVING_LICENSE, UNKNOWN

Examples:
- "Reg. 136 A ... REGISTRATION OF PERSONS ACT ... IDENTITY CARD" → ID_APPLICATION
- "LAND CONTROL ACT ... APPLICATION FOR CONSENT" → LAND_BOARD
- "Form B3 ... APPLICATION FOR LATE REGISTRATION OF A BIRTH" → BIRTH_LATE_REGISTRATION
- "Form B1 ... REGISTRATION OF BIRTH" → BIRTH_CERTIFICATE
- "KRA PIN APPLICATION FORM ... iTax" → KRA_PIN

OCR Text:
{ocr_text}

Return ONLY valid JSON with NO other text:
{{"form_type": "...", "confidence": 0.95, "reasoning": "matched keywords ..."}}
"""  # noqa: E501


def detect_form_type_prompt(
    ocr_text: str,
    *,
    language: Language = "English",
) -> str:
    """Build the prompt for form type detection."""
    return FORM_TYPE_PROMPT_TEMPLATE.format(
        system=SYSTEM_PROMPT,
        ocr_text=ocr_text[:1500],
    )


# ── Field Extraction ────────────────────────────────────────────────

FIELD_EXTRACTION_PROMPT_TEMPLATE = """{system}
{lang}

Form: {form_type}
{labels_section}

OCR: {ocr_text}

Extract fields as JSON array:
[{{"label":"..","value":"..","confidence":0.9,"field_type":"text"}}]
JSON:"""  # noqa: E501

FIELD_EXTRACTION_NO_TEMPLATE = """When no known form labels are provided, infer field names from the
OCR text itself. Look for section headers, underlined text, and
label-value pairs. Use the English label text as-is."""  # noqa: E501


def extract_fields_prompt(
    ocr_text: str,
    form_type: FormType,
    *,
    language: Language = "English",
    known_labels: list[str] | None = None,
) -> str:
    """Build the prompt for field extraction."""
    lang = "Swahili" if language == "Swahili" else "English"
    if known_labels:
        labels_section = f"Known field labels: {', '.join(known_labels)}"
    else:
        labels_section = FIELD_EXTRACTION_NO_TEMPLATE
    return FIELD_EXTRACTION_PROMPT_TEMPLATE.format(
        system=SYSTEM_PROMPT,
        lang=lang,
        form_type=form_type.value,
        labels_section=labels_section,
        ocr_text=ocr_text[:1500],
    )


# ── Language Detection ──────────────────────────────────────────────


def detect_language_prompt(ocr_text: str) -> str:
    """Build a prompt to detect the form's primary language.

    Args:
        ocr_text: OCR text from the form.

    Returns:
        Formatted prompt string.
    """
    return f"""Detect whether the following form text is primarily in English or Swahili.

OCR Text:
{ocr_text[:1000]}

Respond with ONLY: "English", "Swahili", or "MIXED"
"""
