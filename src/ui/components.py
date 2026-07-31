"""Streamlit UI components for displaying and editing extracted fields.

Provides reusable components for the Karatasi form processing interface,
supporting English and Swahili display.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import streamlit as st

from src.forms.fields import ExtractedField
from src.ocr.preprocess import BoundingBox
from src.pipeline import PipelineResult, re_extract_fields

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.ui.strings import Strings


# ── Region overlay colors (BGR for cv2) ──────────────────────────────

_REGION_COLORS: dict[str, tuple[int, int, int]] = {
    "label": (46, 125, 50),       # green
    "field": (21, 101, 192),      # blue
    "checkbox": (230, 81, 0),     # orange
    "signature": (106, 27, 154),  # purple
    "photo": (198, 40, 40),       # red
    "unknown": (97, 97, 97),      # gray
}


# ── Helpers ──────────────────────────────────────────────────────────


def _change_language() -> None:
    """Callback: switch UI language."""
    st.session_state.language = st.session_state._lang_selector


# ── Sidebar ──────────────────────────────────────────────────────────


def language_selector() -> str:
    """Render the language selector in the sidebar.

    Returns:
        The selected language ("English" or "Swahili").
    """
    langs = ["English", "Swahili"]
    idx = langs.index(st.session_state.language) if st.session_state.language in langs else 0

    st.selectbox(
        "Language / Lugha",
        options=langs,
        index=idx,
        key="_lang_selector",
        on_change=_change_language,
    )
    return st.session_state.language


def _load_preview_bytes(path: str) -> bytes | None:
    """Render the original upload as PNG bytes for the preview panel.

    PDFs are rendered via their first page; images are encoded directly.
    Returns None when the file cannot be read.
    """
    try:
        if Path(path).suffix.lower() == ".pdf":
            import fitz

            doc = fitz.open(path)
            try:
                return doc[0].get_pixmap(dpi=150).tobytes("png")
            finally:
                doc.close()
        else:
            import cv2

            img = cv2.imread(path)
            if img is None:
                return None
            ok, encoded = cv2.imencode(".png", img)
            return encoded.tobytes() if ok else None
    except Exception:
        logger.exception("Failed to load preview for %s", path)
        return None


def _render_regions_overlay(
    preprocessed: np.ndarray, regions: list[BoundingBox]
) -> bytes:
    """Draw color-coded region boxes on the preprocessed image.

    Args:
        preprocessed: Binarized image in region coordinate space.
        regions: Layout regions detected on the form.

    Returns:
        PNG bytes for st.image.
    """
    import cv2

    img = cv2.cvtColor(preprocessed, cv2.COLOR_GRAY2RGB)
    for region in regions:
        color = _REGION_COLORS.get(region.region_type, _REGION_COLORS["unknown"])
        cv2.rectangle(
            img,
            (region.x, region.y),
            (region.x + region.w, region.y + region.h),
            color,
            2,
        )
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("Failed to encode regions overlay image")
    return encoded.tobytes()


def _regions_legend(s: Strings) -> None:
    """Render a color legend for the regions overlay."""
    from src.ui.strings import get_region_type_label

    lang = st.session_state.language
    spans = []
    for region_type, (b, g, r) in _REGION_COLORS.items():
        spans.append(
            f'<span style="color:rgb({r},{g},{b}); margin-right:12px;">'
            f"■ {get_region_type_label(region_type, lang)}</span>"
        )
    st.markdown(" ".join(spans), unsafe_allow_html=True)


@st.fragment
def display_preview(
    result: PipelineResult,
    original_path: str | None,
    s: Strings,
) -> None:
    """Show the original scan and a color-coded regions overlay."""
    if original_path is None:
        return

    with st.expander(s.original_scan, expanded=False):
        preview_bytes = _load_preview_bytes(original_path)
        if preview_bytes is None:
            st.info(s.no_preview_message)
        else:
            st.image(preview_bytes, use_container_width=True)

    if result.layout and result.layout.regions:
        with st.expander(s.regions_header, expanded=False):
            if result.preprocessed is None:
                st.info(s.no_regions_message)
            else:
                overlay = _render_regions_overlay(
                    result.preprocessed, result.layout.regions
                )
                st.image(overlay, use_container_width=True)
                _regions_legend(s)


def render_toggles(s: Strings) -> tuple[bool, bool]:
    """Render the TrOCR and LLM toggle checkboxes in the sidebar.

    Returns:
        (use_trocr, use_llm) based on checkbox state.
    """
    st.markdown(f"**{s.options_header if hasattr(s, 'options_header') else 'Options'}**")
    use_trocr = st.checkbox(
        s.use_trocr_label,
        value=st.session_state.get("_use_trocr", False),
        key="_use_trocr",
        help="Enable TrOCR handwriting recognition on field regions. Adds ~70s and ~1.5GB RAM.",
    )
    use_llm = st.checkbox(
        s.use_llm_label,
        value=st.session_state.get("_use_llm", False),
        key="_use_llm",
        help="Use the local LLM for field value extraction. Adds ~3s and ~2.5GB RAM.",
    )
    return use_trocr, use_llm


def render_sidebar_info(result: PipelineResult | None, s: Strings) -> None:
    """Render sidebar metadata about the processed form."""
    if result is None:
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{s.form_type_label}**")

    from src.ui.strings import get_form_type_label

    st.sidebar.write(get_form_type_label(result.form_type, st.session_state.language))
    st.sidebar.write(f"{s.confidence_label}: {result.form_type_confidence:.0%}")

    if result.fields:
        avg_conf = result.mean_confidence
        st.sidebar.write(f"{s.avg_confidence_label}: {avg_conf:.0%}")

    st.sidebar.write(f"{s.processing_time_label}: {result.elapsed_ms / 1000:.1f}s")

    if result.page_count > 1:
        st.sidebar.write(f"📄 {s.pages_label}: {result.page_count}")


# ── Form Display ─────────────────────────────────────────────────────


@st.fragment
def display_fields(result: PipelineResult, s: Strings) -> list[ExtractedField]:
    """Display extracted fields in an editable form layout.

    Each field shows its label, confidence indicator, and an editable input.
    Validation errors are shown inline. Returns the updated field list.

    Args:
        result: Pipeline result with extracted fields.
        s: UI strings for the current language.

    Returns:
        Updated list of ExtractedField with any user edits applied.
    """
    if not result.fields:
        st.info(s.no_fields_message)
        return []

    fields = result.fields
    for i, field in enumerate(fields):
        label = field.label_sw if st.session_state.language == "Swahili" else field.label_en
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            display_label = f"**{label}**"
            if field.is_handwritten:
                display_label += f" ({s.handwritten_label})"
            st.markdown(display_label)

        with col2:
            _confidence_badge(field.confidence)

        with col3:
            st.text_input(
                s.value_label,
                value=field.value,
                key=f"_field_edit_{i}",
                label_visibility="collapsed",
            )

        with col4:
            st.checkbox(
                s.verified_label,
                value=field.validated,
                key=f"_field_valid_{i}",
                label_visibility="collapsed",
            )

    # Collect edited values and verified flags, then rebuild fields
    edited_values = {
        i: st.session_state.get(f"_field_edit_{i}", field.value)
        for i, field in enumerate(fields)
    }
    validated_values = {
        i: st.session_state.get(f"_field_valid_{i}", field.validated)
        for i, field in enumerate(fields)
    }
    return _rebuild_fields(fields, edited_values, validated_values)


def _rebuild_fields(
    fields: list[ExtractedField],
    edited_values: dict[int, str],
    validated_values: dict[int, bool],
) -> list[ExtractedField]:
    """Rebuild fields applying user edits and verified flags.

    Every attribute except value/validated is preserved via
    dataclasses.replace (region_id, confidence, is_handwritten, field_type).
    """
    updated: list[ExtractedField] = []
    for i, field in enumerate(fields):
        updated.append(
            dataclasses.replace(
                field,
                value=edited_values.get(i, field.value),
                validated=validated_values.get(i, field.validated),
            )
        )
    return updated


@st.fragment
def display_form_summary(result: PipelineResult, s: Strings) -> None:
    """Show a compact summary card for the processed form."""
    from src.ui.strings import get_form_type_label

    st.markdown(f"### {s.detected_form_label}")
    cols = st.columns(4)
    cols[0].metric(s.form_type_label, get_form_type_label(result.form_type, st.session_state.language))
    cols[1].metric(s.confidence_label, f"{result.form_type_confidence:.0%}")
    cols[2].metric(s.fields_label, str(len(result.fields)))
    cols[3].metric(s.processing_time_label, f"{result.elapsed_ms / 1000:.1f}s")


# ── Form Type Override ────────────────────────────────────────────────


@st.fragment
def render_form_type_override(result: PipelineResult, s: Strings) -> None:
    """Show a form type override dropdown to re-extract fields with a different type.

    When the user selects a different form type and clicks apply,
    field extraction is re-run with the selected type and the
    session state is updated.
    """
    from src.llm.prompts import FormType
    from src.ui.strings import get_form_type_label

    current = result.form_type.value
    options = [ft.value for ft in FormType]
    # Order so the current selection comes first for readability
    display = [get_form_type_label(ft.value, st.session_state.language) for ft in FormType]
    current_idx = options.index(current) if current in options else 0

    st.markdown(f"**{s.override_form_type}**")
    cols = st.columns([3, 1])
    with cols[0]:
        selected_label = st.selectbox(
            s.override_form_type,
            options=display,
            index=current_idx,
            key="ft_override_select",
            label_visibility="collapsed",
        )
    with cols[1]:
        apply = st.button(s.override_apply_label or "Apply", use_container_width=True, key="ft_override_btn")

    if apply:
        selected_value = options[display.index(selected_label)]
        if selected_value == current:
            return

        from src.llm.prompts import FormType as FT

        new_type = FT(selected_value)
        try:
            new_result = re_extract_fields(
                result, new_type, language=st.session_state.language
            )
            st.session_state.result = new_result
            st.rerun()
        except Exception as exc:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Form type re-extraction failed")
            st.error(f"{s.error_label}: {exc}")


# ── Export ────────────────────────────────────────────────────────────


@st.fragment
def render_export_buttons(result: PipelineResult, original_path: str | None, s: Strings) -> None:
    """Render download buttons for PDF and JSON export.

    Args:
        result: Pipeline result with extracted fields.
        original_path: Path to the original uploaded file (for PDF overlay).
        s: UI strings for the current language.
    """
    if original_path is None:
        return

    col1, col2 = st.columns(2)

    # ── PDF export ────────────────────────────────────────────────
    with col1:
        try:
            from src.export.pdf import pdf_bytes

            pdf_data = pdf_bytes(result, original_path)
            st.download_button(
                label=f"📄 {s.download_pdf_label}",
                data=pdf_data,
                file_name=f"karatasi_filled_{result.form_type.value.lower()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            st.button(
                f"📄 {s.download_pdf_label} ({s.error_label})",
                disabled=True,
                use_container_width=True,
            )

    # ── JSON export ───────────────────────────────────────────────
    with col2:
        try:
            from src.export.json_export import json_bytes

            language = st.session_state.get("language", "English")
            json_data = json_bytes(result, language=language)
            st.download_button(
                label=f"📋 {s.download_json_label}",
                data=json_data,
                file_name=f"karatasi_{result.form_type.value.lower()}.json",
                mime="application/json",
                use_container_width=True,
            )
        except Exception:
            st.button(
                f"📋 {s.download_json_label} ({s.error_label})",
                disabled=True,
                use_container_width=True,
            )


# ── Internal Components ──────────────────────────────────────────────


def _confidence_badge(confidence: float) -> None:
    """Render a small coloured confidence indicator."""
    if confidence >= 0.9:
        color = "green"
        label = f"{confidence:.0%}"
    elif confidence >= 0.7:
        color = "orange"
        label = f"{confidence:.0%}"
    else:
        color = "red"
        label = f"{confidence:.0%}"

    st.markdown(
        f'<span style="color:{color}; font-weight:bold;">{label}</span>',
        unsafe_allow_html=True,
    )



