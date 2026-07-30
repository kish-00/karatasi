"""JSON export for extracted form data.

Produces structured JSON conforming to the output schema
described in the project critique.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.forms.fields import ExtractedField
from src.pipeline import PipelineResult


def export_to_json(result: PipelineResult, language: str = "English") -> dict[str, Any]:
    """Convert a PipelineResult to a JSON-serializable dict.

    Args:
        result: The pipeline output to export.
        language: Output language ("English" or "Swahili").

    Returns:
        Dict matching the project's output schema.
    """
    fields_json: list[dict[str, Any]] = []
    for f in result.fields:
        source = _determine_source(f)
        flag = _determine_flag(f)
        fields_json.append({
            "key": f.key,
            "label": f.label_en,
            "label_sw": f.label_sw,
            "value": f.value,
            "source": source,
            "confidence": round(f.confidence, 3),
            "field_type": f.field_type.value if f.field_type else "text",
            "is_handwritten": f.is_handwritten,
            "validated": f.validated,
            "flag": flag,
        })

    return {
        "form_type": result.form_type.value if result.form_type else "UNKNOWN",
        "form_type_confidence": round(result.form_type_confidence, 3),
        "language": language,
        "processed_at": datetime.now().isoformat(),
        "elapsed_ms": round(result.elapsed_ms, 1),
        "is_web_portal": result.is_web_portal,
        "field_count": len(fields_json),
        "mean_confidence": round(result.mean_confidence, 3),
        "fields": fields_json,
    }


def _determine_source(field: ExtractedField) -> str:
    """Determine whether a field was printed, handwritten, or empty."""
    if not field.value.strip():
        return "empty"
    if field.is_handwritten:
        return "handwritten"
    return "printed"


def _determine_flag(field: ExtractedField) -> str | None:
    """Determine if a field needs a confidence flag."""
    if field.confidence < 0.4:
        return "low_confidence"
    if field.confidence < 0.7:
        return "medium_confidence"
    return None


def write_json(result: PipelineResult, output_path: str | Path, language: str = "English") -> Path:
    """Write pipeline result to a JSON file.

    Args:
        result: Pipeline output.
        output_path: Destination path for the JSON file.
        language: Output language ("English" or "Swahili").

    Returns:
        The output path.
    """
    data = export_to_json(result, language=language)
    output_path = Path(output_path)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return output_path


def json_bytes(result: PipelineResult, language: str = "English") -> bytes:
    """Return pipeline result as JSON bytes (for Streamlit download).

    Args:
        result: Pipeline output.
        language: Output language ("English" or "Swahili").

    Returns:
        JSON bytes.
    """
    data = export_to_json(result, language=language)
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
