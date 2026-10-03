"""
Shared visual design system, color tokens, and Plotly theme presets.
Enforces consistent color semantics across all charts, maps, and metric badges.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import streamlit as st
import plotly.graph_objects as go
from app.ui.css import inject_css


# --- 1. Semantic Color Tokens ---

# Fuel Palette (used uniformly across tables, charts, and map routes)
FUEL_COLORS: Dict[str, str] = {
    "HFO": "#2b2d42",        # Dark Slate / Conventional
    "MGO": "#4a4e69",        # Low-sulfur Marine Gasoil
    "LNG": "#457b9d",        # Steel Blue / Cryogenic fossil/bio
    "Bio_LNG": "#1d3557",    # Deep Blue
    "Methanol": "#2a9d8f",   # Sea Green / E-fuel
    "Ammonia": "#e76f51",    # Burnt Coral / Zero-carbon nitrogen
    "Hydrogen": "#7209b7",   # Vivid Violet / Cryogenic zero-carbon
}

# Metric Palette
METRIC_COLORS: Dict[str, str] = {
    "fuel": "#457b9d",
    "cost": "#e63946",
    "emissions": "#2a9d8f",
    "carbon_intensity": "#1d3557",
    "pass": "#2a9d8f",
    "fail": "#e63946",
}

# Algorithm Palette
ALGO_COLORS: Dict[str, str] = {
    "QIEA (Quantum-Inspired)": "#0f4c81",
    "Genetic Algorithm (GA)": "#2a9d8f",
    "Particle Swarm (PSO)": "#e76f51",
    "Hill-Climb Search": "#7209b7",
    "Random Search": "#6c757d",
}

# Base UI Palette
UI_COLORS: Dict[str, str] = {
    "primary": "#0f4c81",
    "background": "#f8f9fa",
    "card_bg": "#ffffff",
    "text": "#1e293b",
    "muted_text": "#64748b",
    "border": "#e2e8f0",
}


def get_fuel_color(fuel_name: str) -> str:
    """Retrieve consistent hex color for any fuel string."""
    for key, color in FUEL_COLORS.items():
        if key.lower() in fuel_name.lower():
            return color
    return "#6c757d"


def apply_theme_layout(
    fig: go.Figure,
    title: str = "",
    xaxis_title: str = "",
    yaxis_title: str = "",
    height: int = 380,
    show_legend: bool = True,
    **kwargs: Any,
) -> go.Figure:
    """
    Standardize Plotly figures with clean layout, informative axes, and consistent typography.
    """
    margin = kwargs.get("margin", dict(l=40, r=20, t=50 if title else (32 if show_legend else 15), b=40))
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=14, color=UI_COLORS["text"], family="Inter, system-ui, sans-serif"),
            x=0.0,
            xanchor="left",
        ) if title else None,
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(size=12, color=UI_COLORS["muted_text"])),
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0",
            showline=True,
            linecolor="#cbd5e1",
            tickfont=dict(size=11, color=UI_COLORS["text"]),
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(size=12, color=UI_COLORS["muted_text"])),
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0",
            showline=True,
            linecolor="#cbd5e1",
            tickfont=dict(size=11, color=UI_COLORS["text"]),
        ),
        margin=margin,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1.0,
            font=dict(size=11, color=UI_COLORS["text"]),
        ) if show_legend else dict(visible=False),
        hoverlabel=dict(
            bgcolor="#ffffff",
            font_size=12,
            font_family="Inter, system-ui, sans-serif",
            bordercolor="#cbd5e1",
        ),
    )
    return fig
