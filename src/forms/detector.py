"""Form type identification.

Detects which Kenyan government form template a scanned document matches.
Uses keyword-based matching as a fast path, with LLM-based detection as
the primary classifier for higher accuracy.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from src.llm.prompts import FormType, detect_form_type_prompt

logger = logging.getLogger(__name__)

Language = Literal["English", "Swahili"]


@dataclass(frozen=True, slots=True)
class FormDetectionResult:
    """Result of form type detection."""

    form_type: FormType
    confidence: float
    method: Literal["keyword", "llm", "fallback"] = "keyword"
    reasoning: str = ""


# ── Keyword Patterns ────────────────────────────────────────────────

_KEYWORD_PATTERNS: dict[FormType, list[str]] = {
    FormType.ID_APPLICATION: [
        r"reg\.?\s*136\s*a",
        r"registration of persons act",
        r"cap\.?\s*107",
        r"usajili wa watu",
        r"identity card",
        r"kitambulisho",
        r"serial no",
        r"fingerprint classification",
    ],
    FormType.LAND_BOARD: [
        r"land control act",
        r"cap\.?\s*302",
        r"land control board",
        r"consent of land",
        r"application for consent",
        r"form\s*1",
    ],
    FormType.BIRTH_CERTIFICATE: [
        r"registration of birth",
        r"form\s*b1",
        r"birth certificate",
        r"department of the registrar-general",
        r"certificate of birth",
    ],
    FormType.BIRTH_LATE_REGISTRATION: [
        r"late registration",
        r"form\s*b3",
        r"application for late registration",
    ],
    FormType.BIRTH_REGISTRATION: [
        r"form\s*a1",
        r"notification of birth",
        r"birth notification",
    ],
    FormType.KRA_PIN: [
        r"kra pin",
        r"pin application",
        r"itax",
        r"kenya revenue authority",
    ],
    FormType.DRIVING_LICENSE: [
        r"driving licence",
        r"driving license",
        r"ntsa",
        r"transport and safety",
        r"driver.*licens",
    ],
}


def _keyword_match(text: str) -> FormDetectionResult | None:
    """Try to detect form type via keyword patterns.

    Returns None if no pattern matches with sufficient confidence.
    """
    text_lower = text.lower()
    best_type = FormType.UNKNOWN
    best_score = 0
    best_pattern = ""

    for form_type, patterns in _KEYWORD_PATTERNS.items():
        score = 0
        matched = []
        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 1
                matched.append(pattern)
        if score > best_score:
            best_score = score
            best_type = form_type
            best_pattern = "; ".join(matched[:3])

    if best_score >= 1:
        confidence = min(0.9, 0.5 + best_score * 0.15)
        return FormDetectionResult(
            form_type=best_type,
            confidence=confidence,
            method="keyword",
            reasoning=f"Matched {best_score} patterns: {best_pattern}",
        )

    return None


# ── Public API ──────────────────────────────────────────────────────


def detect_form_type(
    ocr_text: str,
    *,
    use_llm: bool = False,
    language: Language = "English",
) -> FormDetectionResult:
    """Identify the form type from OCR text.

    Uses keyword matching as fast path, optionally falls back to LLM.

    Args:
        ocr_text: Full OCR text output from a scanned form.
        use_llm: If True, use LLM for detection when keyword match is weak.
        language: Output language for LLM reasoning.

    Returns:
        FormDetectionResult with form type and confidence.
    """
    # Fast path: keyword matching
    keyword_result = _keyword_match(ocr_text)
    if keyword_result is not None and keyword_result.confidence >= 0.8:
        return keyword_result

    # LLM path
    if use_llm:
        try:
            from src.llm.serve import get_server

            server = get_server()
            prompt = detect_form_type_prompt(ocr_text, language=language)
            result = server.infer(prompt, max_tokens=256)

            if result.text:
                parsed = _parse_json(result.text)
                if parsed and "form_type" in parsed:
                    ft = parsed["form_type"].upper().replace(" ", "_")
                    if ft in FormType._value2map_:
                        conf = float(parsed.get("confidence", 0.5))
                        reasoning = parsed.get("reasoning", "")
                        return FormDetectionResult(
                            form_type=FormType(ft),
                            confidence=conf,
                            method="llm",
                            reasoning=reasoning,
                        )
        except Exception:
            logger.exception("LLM form type detection failed")

    # Fallback: use keyword result even if low confidence
    if keyword_result is not None:
        return keyword_result

    return FormDetectionResult(
        form_type=FormType.UNKNOWN,
        confidence=0.0,
        method="fallback",
        reasoning="No matching patterns found",
    )


def _parse_json(text: str) -> dict | None:
    """Find and parse a JSON object anywhere in LLM output text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
