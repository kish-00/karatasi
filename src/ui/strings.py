"""English and Swahili UI string translations.

All user-facing strings in the Streamlit UI are defined here.
Import the active language's strings using `get_strings(language)`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Literal

Language = Literal["English", "Swahili"]


def _build(lang: Language) -> SimpleNamespace:
    """Build a namespace of UI strings for the given language.

    Every attribute is a user-facing string used by Streamlit components.
    """
    en_str = "English"

    def s(e: str, sw_v: str) -> str:
        return e if lang == en_str else sw_v

    return SimpleNamespace(
        # ── App ──
        app_title=s("Karatasi — Automatic Form Filling", "Karatasi — Kujaza Fomu Kiotomatiki"),
        app_subtitle=s(
            "Offline AI document processor for Kenyan government forms",
            "Kichakata hati cha AI bila mtandao kwa fomu za serikali ya Kenya",
        ),
        built_for_adtc=s(
            "Built for the Africa Deep Tech Challenge 2026 — running fully offline on an 8 GB laptop.",
            "Imejengwa kwa Africa Deep Tech Challenge 2026 — inafanya kazi bila mtandao kwenye laptop ya 8 GB.",
        ),
        # ── Options (toggles) ──
        options_header=s("Options", "Chaguo"),
        use_trocr_label=s("Handwriting OCR (TrOCR, ~70s, +1.5GB)", "OCR ya Mwandiko (TrOCR, ~70s, +1.5GB)"),
        use_llm_label=s("LLM Field Extraction (~3s, +2.5GB)", "Uchimbaji wa LLM (~3s, +2.5GB)"),
        # ── Upload ──
        upload_header=s("Upload a Form", "Pakia Fomu"),
        upload_label=s(
            "Upload a scanned form (PDF, JPG, or PNG)",
            "Pakia fomu iliyoskana (PDF, JPG, au PNG)",
        ),
        upload_help=s(
            "Supports PDF, JPG, and PNG files up to 20 MB",
            "Inasaidia faili za PDF, JPG, na PNG hadi MB 20",
        ),
        process_button_label=s("Process Form", "Chakata Fomu"),
        processing_label=s(
            "Processing… This may take a moment.",
            "Inachakatwa… Hii inaweza kuchukua muda.",
        ),
        # ── Web portal ──
        web_portal_message=s(
            "This PDF appears to be a web portal page, not a scanned form.",
            "PDF hii inaonekana ni ukurasa wa wavuti, si fomu iliyoskana.",
        ),
        reset_button_label=s("Reset", "Weka upya"),
        # ── Form type ──
        detected_form_label=s("Detected Form", "Fomu Iliyotambuliwa"),
        form_type_label=s("Form Type", "Aina ya Fomu"),
        confidence_label=s("Confidence", "Uhakika"),
        override_form_type=s("Override form type (if incorrect)", "Badilisha aina ya fomu (ikiwa si sahihi)"),
        override_apply_label=s("Apply", "Weka"),
        fields_label=s("Fields", "Sehemu"),
        processing_time_label=s("Time", "Muda"),
        # ── Fields ──
        extracted_fields_label=s("Extracted Fields", "Sehemu Zilizotolewa"),
        field_label=s("Field", "Sehemu"),
        value_label=s("Value", "Thamani"),
        field_confidence=s("Confidence", "Uhakika"),
        handwritten_label=s("Handwritten", "Imeandikwa kwa mkono"),
        avg_confidence_label=s("Avg Confidence", "Wastani wa Uhakika"),
        no_fields_message=s(
            "No fields extracted for this form type.",
            "Hakuna sehemu zilizotolewa kwa aina hii ya fomu.",
        ),
        # ── Preview ──
        original_scan=s("Original Scan", "Skana Asili"),
        # ── Export ──
        export_header=s("Export", "Toa"),
        download_pdf_label=s("Download PDF", "Pakua PDF"),
        download_json_label=s("Download JSON", "Pakua JSON"),
        export_success=s("Download ready", "Upakuaji uko tayari"),
        # ── Language ──
        language_label=s("Language", "Lugha"),
        # ── OCR ──
        # ── Warnings ──
        blur_warning_header=s("Blur Detection", "Ugunduzi wa Ukungu"),
        rotate_warning_header=s("Rotation", "Mzunguko"),
        non_form_warning_header=s("Not a Form?", "Si Fomu?"),
        raw_ocr_label=s("Raw OCR Text", "Maandishi ya OCR"),
        no_ocr_text=s("No OCR text available.", "Hakuna maandishi ya OCR."),
        # ── Errors ──
        error_label=s("Error", "Hitilafu"),
        error_no_file=s("Please upload a form to begin.", "Tafadhali pakia fomu kuanza."),
        error_processing=s(
            "An error occurred while processing the form.",
            "Hitilafu imetokea wakati wa kuchakata fomu.",
        ),
        error_file_too_large=s(
            "File is too large (>20MB). Please downscale to under 20MB.",
            "Faili ni kubwa sana (>20MB). Tafadhali punguza ukubwa hadi chini ya 20MB.",
        ),
        error_unsupported_format=s(
            "Unsupported file format. Please upload a PDF, JPG, or PNG.",
            "Fomati ya faili haitumiki. Tafadhali pakia PDF, JPG, au PNG.",
        ),
        retry=s("Try again", "Jaribu tena"),
        # ── Instructions ──
        how_it_works=s("How it works", "Jinsi inavyofanya kazi"),
        step1=s("Upload a scan or photo of any Kenyan government form", "Pakia skana au picha ya fomu yoyote ya serikali ya Kenya"),
        step2=s("AI detects the form type and reads typed and handwritten fields", "AI inatambua aina ya fomu na kusoma sehemu zilizochapishwa na zilizoandikwa kwa mkono"),
        step3=s("Review and edit extracted fields in English or Swahili", "Kagua na hariri sehemu zilizotolewa kwa Kiingereza au Kiswahili"),
        step4=s("Export a filled PDF or structured JSON", "Toa PDF iliyojazwa au JSON iliyopangwa"),
    )


# Cache per language so we only build once per session
_cache: dict[str, SimpleNamespace] = {}


def get_strings(language: Language) -> SimpleNamespace:
    """Get all UI strings in the specified language.

    Returns a SimpleNamespace with attribute access for all UI strings.
    """
    if language not in _cache:
        _cache[language] = _build(language)
    return _cache[language]


# ── Form-type labels ─────────────────────────────────────────────────

_FORM_TYPE_LABELS: dict[str, dict[Language, str]] = {
    "ID_APPLICATION": {
        "English": "ID Application (Form 136A)",
        "Swahili": "Maombi ya Kitambulisho (Fomu 136A)",
    },
    "LAND_BOARD": {
        "English": "Land Control Board Consent",
        "Swahili": "Ridhaa ya Bodi ya Ardhi",
    },
    "BIRTH_CERTIFICATE": {
        "English": "Birth Certificate",
        "Swahili": "Cheti cha Kuzaliwa",
    },
    "BIRTH_LATE_REGISTRATION": {
        "English": "Late Birth Registration (Form B3)",
        "Swahili": "Usajili wa Kuzaliwa Marehemu (Fomu B3)",
    },
    "BIRTH_REGISTRATION": {
        "English": "Birth Registration (Form A1)",
        "Swahili": "Usajili wa Kuzaliwa (Fomu A1)",
    },
    "KRA_PIN": {
        "English": "KRA PIN Application",
        "Swahili": "Maombi ya KRA PIN",
    },
    "DRIVING_LICENSE": {
        "English": "Driving License Application",
        "Swahili": "Maombi ya Leseni ya Udereva",
    },
    "UNKNOWN": {
        "English": "Unrecognized Form (inferred fields)",
        "Swahili": "Fomu Isiyotambulika (sehemu zilizokadiriwa)",
    },
}

_FIELD_SOURCE_LABELS: dict[str, dict[Language, str]] = {
    "printed": {
        "English": "Printed (typed)",
        "Swahili": "Imechapishwa",
    },
    "handwritten": {
        "English": "Handwritten",
        "Swahili": "Imeandikwa kwa mkono",
    },
    "empty": {
        "English": "Empty (not filled)",
        "Swahili": "Tupu (hajajazwa)",
    },
}


def get_form_type_label(form_type: str, language: Language) -> str:
    """Get a human-readable label for a form type in the given language."""
    return _FORM_TYPE_LABELS.get(form_type, {}).get(language, form_type)


def get_source_label(source: str, language: Language) -> str:
    """Get a human-readable source label."""
    return _FIELD_SOURCE_LABELS.get(source, {}).get(language, source)
