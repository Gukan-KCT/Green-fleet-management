"""
CSS injection helper for Green Fleet.
Standalone module — imports only stdlib + streamlit.
Call inject_css() once per page after set_page_config().
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st

_CSS_PATH = Path(__file__).parent / "style.css"


def inject_css() -> None:
    """
    Injects the shared Green Fleet design-system CSS and Google Fonts (Inter)
    into the current Streamlit page. Call once after set_page_config().
    """
    # Google Fonts preconnect + Inter stylesheet
    fonts_html = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter'
        ':wght@400;500;600;700&display=swap" rel="stylesheet">'
    )
    st.markdown(fonts_html, unsafe_allow_html=True)

    if _CSS_PATH.exists():
        css_text = _CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)
