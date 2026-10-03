"""
Alternative Fuels - Techno-Economic Marine Fuel Assessment.
Compares energy density, bunkering cost, lifecycle emissions, and cargo volume loss.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Alternative Fuels | Green Fleet",
    page_icon="🌱",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, get_fuel_color
from app.ui.state import get_default_config
from src.analysis.fuels import compare_fuels_for_voyage

render_top_strip(
    title="Alternative Marine Fuels",
    subtitle="Evaluate volumetric energy density, lifecycle emissions, and cargo slot displacement.",
)

cfg = get_default_config()

# --- 1. Controls ---
c_v, c_r, c_p = st.columns([1, 1, 1])

vessel_types = list(cfg["vessel_types"].keys())
vessel_names = {k: cfg["vessel_types"][k]["name"] for k in vessel_types}

route_keys = list(cfg["routes"].keys())
route_names = {k: f"{k}: {cfg['routes'][k]['name']}" for k in route_keys}

with c_v:
    vessel_sel = st.selectbox(
        "Vessel Class",
        options=vessel_types,
        format_func=lambda x: vessel_names[x],
        help="Target vessel archetype for bunkering evaluation.",
    )
with c_r:
    route_sel = st.selectbox(
        "Corridor",
        options=route_keys,
        format_func=lambda x: route_names[x],
        help="Shipping lane distance and sea state.",
    )
with c_p:
    pathway_sel = st.selectbox(
        "Production Pathway",
        options=["green", "blue", "grey"],
        index=0,
        help="Upstream feedstocks: Green (electrolysis/e-fuel), Blue (fossil+CCS), Grey (unabated fossil).",
    )

pathways = {f: pathway_sel for f in ["Methanol", "Ammonia", "Hydrogen"]}

# Compute Fuel Comparison DataFrame
fuels_df = compare_fuels_for_voyage(
    vessel_key=vessel_sel,
    route_key=route_sel,
    pathway_choices=pathways,
    config=cfg,
)

# --- 2. Fuel KPI Cards Grid ---
st.caption(f"Showing comparative performance for {vessel_names[vessel_sel]} on {route_names[route_sel]} ({pathway_sel.upper()} pathway):")

f_cols = st.columns(len(fuels_df))
for i, (_, row) in enumerate(fuels_df.iterrows()):
    f_name = str(row["fuel_type"])
    color = get_fuel_color(f_name)
    with f_cols[i]:
        with st.container(border=True):
            st.markdown(f"<span style='color:{color}; font-weight:bold;'>● {f_name}</span>", unsafe_allow_html=True)
            st.metric(
                label="Bunker Mass",
                value=f"{row['fuel_mass_tonnes']:,.1f} t",
                help="Total required fuel mass accounting for Lower Heating Value (LHV) equivalence.",
            )
            st.metric(
                label="Voyage Cost",
                value=f"${int(row['fuel_cost_usd']):,}",
                help="Bunkering procurement expenditure.",
            )
            st.metric(
                label="Lifecycle CO2e",
                value=f"{int(row['lifecycle_co2e_tonnes']):,} t",
                help="Well-to-Wake total lifecycle emissions.",
            )
            st.caption(f"Cargo penalty: **{row['cargo_loss_pct']:.1f}%**")

# --- 3. Focused Comparative Charts (2x2 Grid) ---
c_ch1, c_ch2 = st.columns(2)

with c_ch1:
    with st.container(border=True):
        st.markdown("**Required Fuel Mass (tonnes)**")
        st.caption("Mass needed to deliver equivalent propulsion energy.")
        fig_mass = go.Figure(
            go.Bar(
                x=fuels_df["fuel_type"],
                y=fuels_df["fuel_mass_tonnes"],
                marker_color=[get_fuel_color(f) for f in fuels_df["fuel_type"]],
                text=[f"{v:,.0f} t" for v in fuels_df["fuel_mass_tonnes"]],
                textposition="auto",
                hovertemplate="%{x}: <b>%{y:,.1f} tonnes</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_mass,
            xaxis_title="Marine Fuel Candidate",
            yaxis_title="Required Mass (tonnes)",
            height=280,
            show_legend=False,
        )
        st.plotly_chart(fig_mass, width="stretch")

with c_ch2:
    with st.container(border=True):
        st.markdown("**Bunker Fuel Procurement Cost ($ USD)**")
        st.caption("Fuel purchasing expenditure based on market/pathway price.")
        fig_cost = go.Figure(
            go.Bar(
                x=fuels_df["fuel_type"],
                y=fuels_df["fuel_cost_usd"],
                marker_color=[get_fuel_color(f) for f in fuels_df["fuel_type"]],
                text=[f"${int(v):,}" for v in fuels_df["fuel_cost_usd"]],
                textposition="auto",
                hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_cost,
            xaxis_title="Marine Fuel Candidate",
            yaxis_title="Bunker Procurement ($ USD)",
            height=280,
            show_legend=False,
        )
        st.plotly_chart(fig_cost, width="stretch")

c_ch3, c_ch4 = st.columns(2)

with c_ch3:
    with st.container(border=True):
        st.markdown("**Well-to-Wake Emissions Breakdown (tonnes CO2e)**")
        st.caption("Tank-to-Wake (combustion) vs Well-to-Tank (upstream production).")
        fig_emiss = go.Figure()
        fig_emiss.add_trace(
            go.Bar(
                x=fuels_df["fuel_type"],
                y=fuels_df["ttw_co2e_tonnes"],
                name="Tank-to-Wake (Combustion)",
                marker_color="#2b2d42",
            )
        )
        fig_emiss.add_trace(
            go.Bar(
                x=fuels_df["fuel_type"],
                y=fuels_df["wtt_co2e_tonnes"],
                name="Well-to-Tank (Upstream)",
                marker_color="#2a9d8f",
            )
        )
        fig_emiss.update_layout(barmode="stack")
        apply_theme_layout(
            fig_emiss,
            xaxis_title="Marine Fuel Candidate",
            yaxis_title="Lifecycle Emissions (tonnes CO2e)",
            height=280,
            show_legend=True,
        )
        st.plotly_chart(fig_emiss, width="stretch")

with c_ch4:
    with st.container(border=True):
        st.markdown("**Cargo Slot Loss / Volumetric Penalty (%)**")
        st.caption("Container slot loss from cryogenic insulation and fuel tank volume.")
        fig_pen = go.Figure(
            go.Bar(
                x=fuels_df["fuel_type"],
                y=fuels_df["cargo_loss_pct"],
                marker_color="#e76f51",
                text=[f"{v:.1f}%" for v in fuels_df["cargo_loss_pct"]],
                textposition="auto",
                hovertemplate="%{x}: <b>%{y:.1f}% capacity loss</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_pen,
            xaxis_title="Marine Fuel Candidate",
            yaxis_title="Usable Capacity Penalty (%)",
            height=280,
            show_legend=False,
        )
        st.plotly_chart(fig_pen, width="stretch")

# Detailed Data Table
with st.expander("Full Techno-Economic Marine Fuel Matrix", expanded=False):
    st.dataframe(
        fuels_df[[
            "fuel_type", "display_name", "pathway", "fuel_mass_tonnes",
            "fuel_cost_usd", "lifecycle_co2e_tonnes", "cargo_loss_pct", "bunkering_feasible"
        ]],
        column_config={
            "fuel_type": st.column_config.TextColumn("Fuel"),
            "display_name": st.column_config.TextColumn("Description"),
            "pathway": st.column_config.TextColumn("Pathway"),
            "fuel_mass_tonnes": st.column_config.NumberColumn("Mass (t)", format="%.1f t"),
            "fuel_cost_usd": st.column_config.NumberColumn("Cost ($)", format="$%d"),
            "lifecycle_co2e_tonnes": st.column_config.NumberColumn("CO2e (t)", format="%.1f t"),
            "cargo_loss_pct": st.column_config.NumberColumn("Slot Penalty", format="%.1f%%"),
            "bunkering_feasible": st.column_config.CheckboxColumn("Port Bunkering Available"),
        },
        hide_index=True,
        width="stretch",
    )
