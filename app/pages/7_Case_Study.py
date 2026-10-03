"""
Case Study - South Asian Feeder Decarbonization Assessment.
Rigorous 4-plan comparison (Naive, Best Conv, Balanced, Green) with Plan Insights,
carbon abatement cost, and monthly weather simulation.
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

from app.ui.components import (
    render_top_strip,
    render_kpi_row,
    render_constraints_table,
    render_plan_insights_card,
    render_carbon_intensity_badge,
)
from app.ui.theme import apply_theme_layout, UI_COLORS
from app.ui.css import inject_css
from app.ui.state import get_or_load_case_study, get_default_config, check_artifact_staleness
from src.analysis.case_study import run_case_study
from src.optimization.problem import FleetOptimizationProblem
from src.analysis.report import generate_html_report, generate_csv_summary

render_top_strip(
    title="Regional Feeder Decarbonization Case Study",
    subtitle="Benchmarking multi-objective optimization against Feasible Naive and Best Conventional references.",
    demo_only=True,
)


inject_css()
cfg = get_default_config()

# --- 1. Load Precomputed Case Study or Compute ---
if check_artifact_staleness("saved_case_study.pkl"):
    st.warning("Saved case study results are out of date, press Re-run to update.", icon="⚠️")

c_stat, c_dl = st.columns([13, 7])
with c_stat:
    st.caption("Case study evaluates a 5-route South Asian feeder network connecting Mumbai, Kochi, Tuticorin, Chennai, Colombo, and Singapore across 4 fleet deployment strategies.")

case_data = get_or_load_case_study()

if case_data is None:
    with st.spinner("Computing regional feeder case study simulation across 4 plans..."):
        case_data = run_case_study(pop_size=40, generations=100, random_seed=42)
        st.session_state["case_study_results"] = case_data

summary = case_data["summary"]
df_routes = case_data["df_routes"]
df_monthly = case_data["df_monthly"]
naive_eval = case_data["naive_eval"]
best_conv_eval = case_data["best_conv_eval"]
balanced_eval = case_data.get("balanced_eval", case_data["optimized_eval"])
green_eval = case_data.get("green_eval", balanced_eval)
problem = case_data.get("problem") or FleetOptimizationProblem(config=cfg)
carbon_price_ref = summary.get("carbon_price_reference_usd", 80.0)

# Plan Insights Card for Balanced Plan
render_plan_insights_card(
    opt_eval=balanced_eval,
    best_conv_eval=best_conv_eval,
    problem=problem,
    carbon_price_ref=carbon_price_ref,
)

# --- 2. 4-Plan Comprehensive Decarbonization Scorecard ---
st.markdown("### Four-Plan Comprehensive Decarbonization Scorecard")

plan_tabs = st.tabs([
    "Balanced Optimized Plan (0.2/0.4/0.4)",
    "Green Optimized Plan (0.1/0.1/0.8)",
    "Best Conventional Baseline",
    "Feasible Naive Baseline",
])

with plan_tabs[0]:
    render_kpi_row(balanced_eval, best_conv_eval, comparator_name="Best Conv")
    b_metrics = summary.get("balanced", summary.get("optimized", {}))
    abat = b_metrics.get("abatement_cost_usd_per_t")
    col_ab1, col_ab2, col_ab3 = st.columns(3)
    with col_ab1:
        st.metric(
            label="Carbon Abatement Cost vs Best Conv",
            value=f"${abat:.1f} / tCO2e" if abat is not None else "N/A (Cost Saving)",
            delta=f"Benchmark: ${carbon_price_ref:.0f}/t carbon price (illustrative)",
            delta_color="off",
        )
    with col_ab2:
        st.metric(
            label="Annual CO2e Emissions Avoided",
            value=f"{b_metrics.get('emissions_avoided_t', 0.0):,.1f} t CO2e",
            delta=b_metrics.get("emissions_label", ""),
            delta_color="normal",
        )
    with col_ab3:
        render_carbon_intensity_badge(balanced_eval["carbon_intensity_g_tnm"])

with plan_tabs[1]:
    render_kpi_row(green_eval, best_conv_eval, comparator_name="Best Conv")
    g_metrics = summary.get("green", summary.get("optimized", {}))
    abat_g = g_metrics.get("abatement_cost_usd_per_t")
    col_ag1, col_ag2, col_ag3 = st.columns(3)
    with col_ag1:
        st.metric(
            label="Carbon Abatement Cost vs Best Conv",
            value=f"${abat_g:.1f} / tCO2e" if abat_g is not None else "N/A",
            delta=f"Benchmark: ${carbon_price_ref:.0f}/t carbon price (illustrative)",
            delta_color="off",
        )
    with col_ag2:
        st.metric(
            label="Annual CO2e Emissions Avoided",
            value=f"{g_metrics.get('emissions_avoided_t', 0.0):,.1f} t CO2e",
            delta=g_metrics.get("emissions_label", ""),
            delta_color="normal",
        )
    with col_ag3:
        render_carbon_intensity_badge(green_eval["carbon_intensity_g_tnm"])

with plan_tabs[2]:
    render_kpi_row(best_conv_eval, naive_eval, comparator_name="Naive")
    st.info("Best Conventional Baseline is the optimal fleet deployment using HFO without shore power.")

with plan_tabs[3]:
    render_kpi_row(naive_eval, naive_eval, comparator_name="Naive")
    st.info("Feasible Naive Baseline uses conventional fixed-speed HFO vessels satisfying all operational constraints.")

opt_eval = balanced_eval

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
            "Naive Vessels": st.column_config.NumberColumn("Naive Vsl", format="%d"),
            "Best Conv Vessels": st.column_config.NumberColumn("Conv Vsl", format="%d"),
            "Balanced Vessels": st.column_config.NumberColumn("Balanced Vsl", format="%d"),
            "Green Vessels": st.column_config.NumberColumn("Green Vsl", format="%d"),
            "Balanced Speed (kn)": st.column_config.NumberColumn("Balanced Speed", format="%.1f kn"),
            "Green Speed (kn)": st.column_config.NumberColumn("Green Speed", format="%.1f kn"),
            "Balanced Oversupply": st.column_config.NumberColumn("Balanced Oversupply", format="%.2fx"),
            "Balanced Reliability (%)": st.column_config.NumberColumn("Reliability", format="%.1f%%"),
        },
        hide_index=True,
        width="stretch",
    )

with st.expander("Regulatory & Operational Constraint Audit", expanded=False):
    render_constraints_table(opt_eval, problem)
