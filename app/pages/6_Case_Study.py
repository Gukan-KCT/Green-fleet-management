"""
Case Study - South Asian Feeder Decarbonization Assessment.
Rigorous dual-baseline comparison (Feasible Naive & Best Conventional) with monthly simulation.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Case Study | Green Fleet",
    page_icon="📑",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip, render_kpi_row, render_constraints_table
from app.ui.theme import apply_theme_layout, UI_COLORS
from app.ui.css import inject_css
from app.ui.state import get_or_load_case_study, get_default_config
from src.analysis.case_study import run_case_study
from src.optimization.problem import FleetOptimizationProblem
from src.analysis.report import generate_html_report, generate_csv_summary

render_top_strip(
    title="Regional Feeder Decarbonization Case Study",
    subtitle="Benchmarking multi-objective optimization against Feasible Naive and Best Conventional references.",
)


inject_css()
cfg = get_default_config()

# --- 1. Load Precomputed Case Study or Compute ---
c_stat, c_dl = st.columns([13, 7])
with c_stat:
    st.caption("Case study evaluates a 5-route South Asian feeder network connecting Mumbai, Kochi, Tuticorin, Chennai, Colombo, and Singapore.")

case_data = get_or_load_case_study()

if case_data is None:
    with st.spinner("Computing regional feeder case study simulation..."):
        case_data = run_case_study(pop_size=40, generations=150, random_seed=42)
        st.session_state["case_study_results"] = case_data

summary = case_data["summary"]
df_routes = case_data["df_routes"]
df_monthly = case_data["df_monthly"]
naive_eval = case_data["naive_eval"]
best_conv_eval = case_data["best_conv_eval"]
opt_eval = case_data["optimized_eval"]
problem = case_data.get("problem") or FleetOptimizationProblem(config=cfg)

# Download Buttons
with c_dl:
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        html_report = generate_html_report(case_data)
        st.download_button(
            label="Download HTML Report",
            data=html_report,
            file_name="green_fleet_case_study_dossier.html",
            mime="text/html",
            width="stretch",
        )
    with col_d2:
        csv_data = generate_csv_summary(case_data)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="green_fleet_case_study_data.csv",
            mime="text/csv",
            width="stretch",
        )

# --- 2. Comparator Toggle & 5 KPI Cards ---
c_comp, _ = st.columns([4, 6])
with c_comp:
    comparator = st.radio(
        "Compare Optimized Plan Against:",
        options=["Feasible Naive Baseline", "Best Conventional Baseline"],
        horizontal=True,
        help="Naive: fixed-speed conventional HFO without shore power. Best Conventional: optimizer restricted to HFO.",
    )

active_baseline = naive_eval if comparator == "Feasible Naive Baseline" else best_conv_eval
comp_name = "Naive" if comparator == "Feasible Naive Baseline" else "Best Conv"

render_kpi_row(opt_eval, active_baseline, comparator_name=comp_name)

# --- 3. Seasonal Trajectory & Route Allocation ---
col_season, col_routes = st.columns([10, 10])

with col_season:
    with st.container(border=True):
        st.markdown("**12-Month Simulated Operational Trajectory**")
        st.caption("Monthly profile adjusted for Indian Ocean monsoon weather severity.")
        fig_mon = go.Figure()
        fig_mon.add_trace(
            go.Scatter(
                x=df_monthly["Month"],
                y=df_monthly["Naive Cost ($M)"],
                mode="lines+markers",
                name="Naive Baseline Cost",
                line=dict(color="#64748b", dash="dash"),
            )
        )
        fig_mon.add_trace(
            go.Scatter(
                x=df_monthly["Month"],
                y=df_monthly["Best Conv Cost ($M)"],
                mode="lines+markers",
                name="Best Conv Cost",
                line=dict(color="#457b9d", dash="dot"),
            )
        )
        fig_mon.add_trace(
            go.Scatter(
                x=df_monthly["Month"],
                y=df_monthly["Optimized Cost ($M)"],
                mode="lines+markers",
                name="Optimized Plan Cost",
                line=dict(color="#0f4c81", width=2.5),
            )
        )
        apply_theme_layout(
            fig_mon,
            xaxis_title="Calendar Month",
            yaxis_title="Monthly OPEX ($ Millions USD)",
            height=300,
            show_legend=True,
        )
        st.plotly_chart(fig_mon, width="stretch")

with col_routes:
    with st.container(border=True):
        st.markdown("**Monthly GHG Emissions Comparison**")
        st.caption("Well-to-Wake monthly emissions across monsoon weather cycles.")
        fig_em = go.Figure()
        fig_em.add_trace(
            go.Bar(
                x=df_monthly["Month"],
                y=df_monthly["Naive CO2e (kt)"],
                name="Naive Baseline",
                marker_color="#cbd5e1",
            )
        )
        fig_em.add_trace(
            go.Bar(
                x=df_monthly["Month"],
                y=df_monthly["Best Conv CO2e (kt)"],
                name="Best Conventional",
                marker_color="#457b9d",
            )
        )
        fig_em.add_trace(
            go.Bar(
                x=df_monthly["Month"],
                y=df_monthly["Optimized CO2e (kt)"],
                name="Optimized Green Plan",
                marker_color="#2a9d8f",
            )
        )
        fig_em.update_layout(barmode="group")
        apply_theme_layout(
            fig_em,
            xaxis_title="Calendar Month",
            yaxis_title="Emissions (kt CO2e)",
            height=300,
            show_legend=True,
        )
        st.plotly_chart(fig_em, width="stretch")

# --- 4. Route Deployment & Compliance Audit ---
st.markdown("### Corridor Allocation & Compliance Verification")

with st.expander("Corridor Operational Profile & Oversupply Ratios Table", expanded=True):
    st.dataframe(
        df_routes,
        column_config={
            "Route ID": st.column_config.TextColumn("Corridor"),
            "Route Name": st.column_config.TextColumn("Lane"),
            "Opt Vessels": st.column_config.NumberColumn("Opt Vessels", format="%d"),
            "Opt Speed (kn)": st.column_config.NumberColumn("Opt Speed", format="%.1f kn"),
            "Opt Oversupply Ratio": st.column_config.NumberColumn("Oversupply", format="%.2fx"),
            "Opt Sailings/Wk": st.column_config.NumberColumn("Sailings/Wk", format="%.2f"),
            "Opt Reliability": st.column_config.NumberColumn("Reliability", format="%.2f"),
        },
        hide_index=True,
        width="stretch",
    )

with st.expander("Regulatory & Operational Constraint Audit", expanded=False):
    render_constraints_table(opt_eval, problem)
