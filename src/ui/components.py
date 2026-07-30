"""Streamlit UI components for displaying and editing extracted fields.

Provides reusable components for the Karatasi form processing interface,
supporting English and Swahili display.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import streamlit as st

from src.forms.fields import ExtractedField
from src.pipeline import PipelineResult, re_extract_fields

if TYPE_CHECKING:
    from src.ui.strings import Strings


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
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            display_label = f"**{label}**"
            if field.is_handwritten:
                display_label += f" ({s.handwritten_label})"
            st.markdown(display_label)

        with col2:
            _confidence_badge(field.confidence)

        with col3:
            original_key = f"_field_orig_{i}"
            st.text_input(
                s.value_label,
                value=field.value,
                key=f"_field_edit_{i}",
                label_visibility="collapsed",
            )
            st.session_state[original_key] = field

    # Collect edited values and rebuild
    updated_fields: list[ExtractedField] = []
    for i, field in enumerate(fields):
        edited = st.session_state.get(f"_field_edit_{i}", field.value)
        updated_fields.append(dataclasses.replace(field, value=edited))

    return updated_fields


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



