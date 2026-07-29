"""Karatasi — Offline AI Document Processor.

Usage:
    streamlit run src/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Karatasi",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────
if "language" not in st.session_state:
    st.session_state.language = "English"
if "form_data" not in st.session_state:
    st.session_state.form_data = None


# ── UI ────────────────────────────────────────────────────────────
st.title("📄 Karatasi")
st.caption(
    "Kujaza Fomu Kiotomatiki — Automatic Form Filling for Kenyan Government Forms"
)

st.info(
    "🚧 Under construction — Week 3 of the build plan."
    " See docs/BUILD_PLAN.md for the full timeline."
)

st.markdown("---")
st.markdown("### How it works")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("**1. Upload**\n\nScan or photo of any Kenyan\ngovernment form")
with col2:
    st.markdown("**2. AI Reads It**\n\nDetects form type, reads typed\nand handwritten fields")
with col3:
    st.markdown("**3. Review & Edit**\n\nCorrect any mistakes\nin English or Swahili")
with col4:
    st.markdown("**4. Export**\n\nDownload filled PDF\nor structured JSON")

st.markdown("---")
st.markdown(
    "Built for the **Africa Deep Tech Challenge 2026** — "
    "running fully offline on an 8GB laptop."
)
