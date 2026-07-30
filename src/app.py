"""Karatasi — Offline AI Document Processor for Kenyan Government Forms.

Usage:
    streamlit run src/app.py
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

from src.pipeline import PipelineResult, process_form
from src.ui.components import (
    display_fields,
    display_form_summary,
    language_selector,
    render_export_buttons,
    render_sidebar_info,
)
from src.ui.strings import get_strings

logger = logging.getLogger(__name__)

# ── Page config (must be first Streamlit call) ──────────────────────

st.set_page_config(
    page_title="Karatasi",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ───────────────────────────────────────────────────

_DEFAULT_STATE: dict[str, object] = {
    "language": "English",
    "result": None,
    "original_path": None,
    "processed": False,
}

for key, default in _DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _clear_state() -> None:
    """Clear session state and clean up temp files."""
    original = st.session_state.original_path
    if original:
        Path(original).unlink(missing_ok=True)
    st.session_state.result = None
    st.session_state.original_path = None
    st.session_state.processed = False


# ── Title ────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='margin-bottom:0;'>📄 Karatasi</h1>"
    "<p style='color:#666; margin-top:0;'>"
    "Kujaza Fomu Kiotomatiki — Automatic Form Filling for Kenyan Government Forms"
    "</p>",
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Karatasi")
    selected_lang = language_selector()

    # Capture the result at render time for sidebar info
    sidebar_result: PipelineResult | None = st.session_state.result
    s = get_strings(selected_lang)
    render_sidebar_info(sidebar_result, s)

    st.markdown("---")
    st.markdown(
        "Built for the **Africa Deep Tech Challenge 2026** — "
        "running fully offline on an 8GB laptop."
    )


# ── Main content ─────────────────────────────────────────────────────

# Check for web portal (from a previous pipeline run stored in session)
result: PipelineResult | None = st.session_state.result
original_path: str | None = st.session_state.original_path

if result and result.is_web_portal:
    st.warning(s.web_portal_message)
    if st.button(s.reset_button_label):
        _clear_state()
        st.rerun()

# ── Upload section ──────────────────────────────────────────────────

st.markdown(f"### {s.upload_header}")

uploaded_file = st.file_uploader(
    s.upload_label,
    type=["pdf", "png", "jpg", "jpeg", "tiff", "tif"],
    help=s.upload_help,
    key="file_uploader",
)

# ── Process button ──────────────────────────────────────────────────

if uploaded_file is not None and not st.session_state.processed:
    if st.button(s.process_button_label, type="primary", use_container_width=True):
        with st.spinner(s.processing_label):
            try:
                # Save uploaded file to a temporary location
                suffix = Path(uploaded_file.name).suffix or ".pdf"
                with tempfile.NamedTemporaryFile(
                    suffix=suffix, delete=False
                ) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                result = process_form(
                    tmp_path,
                    language=st.session_state.language,
                    use_llm=True,
                    use_trocr=True,
                )

                st.session_state.result = result
                st.session_state.original_path = tmp_path
                st.session_state.processed = True
                st.rerun()
            except Exception as exc:
                logger.exception("Pipeline processing failed")
                st.error(f"{s.error_label}: {exc}")

# ── Results display ─────────────────────────────────────────────────

result = st.session_state.result
original_path = st.session_state.original_path

if result and not result.is_web_portal:
    s = get_strings(st.session_state.language)

    # Summary row
    display_form_summary(result, s)

    # Editable fields
    st.markdown(f"### {s.extracted_fields_label}")
    updated_fields = display_fields(result, s)

    # ── Export section ─────────────────────────────────────────────
    st.markdown(f"### {s.export_header}")
    export_result = PipelineResult(
        form_type=result.form_type,
        form_type_confidence=result.form_type_confidence,
        fields=updated_fields,
        layout=result.layout,
        full_text=result.full_text,
        is_web_portal=result.is_web_portal,
        elapsed_ms=result.elapsed_ms,
    )
    render_export_buttons(export_result, original_path, s)

    # ── Raw OCR text (expandable) ──────────────────────────────────
    with st.expander(s.raw_ocr_label):
        st.text(result.full_text or s.no_ocr_text)

    # ── Reset ─────────────────────────────────────────────────────
    if st.button(s.reset_button_label, type="secondary"):
        _clear_state()
        st.rerun()
