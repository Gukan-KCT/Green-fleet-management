"""
Case Study Page - Regional Feeder Decarbonization & Report Export.
"""

import sys
from pathlib import Path
import pickle
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config
from src.analysis.case_study import run_case_study
from src.analysis.report import generate_html_report, generate_csv_summary

st.set_page_config(page_title="Case Study | Green Fleet", page_icon="🚢", layout="wide")

st.title("🚢 Regional Feeder Network Case Study")
st.markdown("Full-scale operational simulation on a 5-corridor Indian Ocean feeder network connecting Nhava Sheva (Mumbai), Kochi, Tuticorin, Chennai, Colombo, and Singapore.")

st.info("**SYNTHETIC NOTICE:** All cargo demands, route distances, bunkering availability, and weather patterns are synthetic illustrative models.")

cfg = load_config()

# Controls
st.sidebar.header("Case Study Controls")
rerun = st.sidebar.button("🔄 Re-run Case Study", width="stretch", type="primary")

saved_case_file = PROJECT_ROOT / "data" / "saved_case_study.pkl"


@st.cache_data(show_spinner="Simulating regional feeder operations with QIEA...")
def get_case_study_data(force_recompute: bool = False):
    if not force_recompute and saved_case_file.exists():
        try:
            with open(saved_case_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return run_case_study(pop_size=50, generations=200, random_seed=42, config=cfg)


if rerun:
    st.cache_data.clear()
    case_data = get_case_study_data(force_recompute=True)
else:
    case_data = get_case_study_data(force_recompute=False)

summary = case_data["summary"]
naive = summary["naive"]
best_conv = summary["best_conventional"]
opt = summary["optimized"]
vs_naive = summary["vs_naive"]
vs_conv = summary["vs_best_conventional"]

df_routes = case_data["df_routes"]
df_monthly = case_data["df_monthly"]

# 1. Executive Headline Comparison
st.subheader("1. Executive Decarbonization & Operating Cost Impact")
st.markdown("Rigorous multi-objective comparison against two feasible reference baselines: **(a) Feasible Naive Baseline** and **(b) Best Conventional Baseline**.")

col_ref = st.radio(
    "Compare Optimized Plan Against:",
    options=["Feasible Naive Baseline (HFO, Fixed Speed)", "Best Conventional Baseline (Optimized HFO)"],
    horizontal=True,
)
selected_ref = "naive" if "Naive" in col_ref else "best_conv"
ref_summary = naive if selected_ref == "naive" else best_conv
ref_deltas = vs_naive if selected_ref == "naive" else vs_conv

k1, k2, k3, k4 = st.columns(4)

f_delta = ref_deltas["fuel_delta_pct"]
c_delta = ref_deltas["cost_delta_pct"]
e_delta = ref_deltas["emissions_delta_pct"]
ci_delta = ref_deltas["ci_delta_pct"]

k1.metric(
    label="Fuel Consumption",
    value=f"{opt['fuel_t']:,.0f} t",
    delta=f"{f_delta:+.1f}% ({'increase' if f_delta > 0 else ('decrease' if f_delta < 0 else 'no change')})",
    help="HFO-equivalent metric tonnes",
)
k2.metric(
    label="Total Operating Cost",
    value=f"${opt['cost_usd'] / 1e6:.1f} M",
    delta=f"{c_delta:+.1f}% ({'increase' if c_delta > 0 else ('decrease' if c_delta < 0 else 'no change')})",
    help="Includes bunker fuel, vessel charter, port fees, shore power, and carbon tax",
)
k3.metric(
    label="Lifecycle GHG Emissions",
    value=f"{opt['emissions_t'] / 1e3:.1f} kt CO2e",
    delta=f"{e_delta:+.1f}% ({'increase' if e_delta > 0 else ('decrease' if e_delta < 0 else 'no change')})",
    help="Well-to-Wake CO2e emissions (propulsion + auxiliary + in-port)",
)
k4.metric(
    label="Fleet Carbon Intensity",
    value=f"{opt['ci_g_tnm']:.2f} g/t-nm",
    delta=f"{ref_deltas['ci_delta_g_tnm']:+.2f} g/t-nm ({'increase' if ci_delta > 0 else ('decrease' if ci_delta < 0 else 'no change')})",
    help="Regulatory proxy cap = 18.0 gCO2e / t-nm",
)

# Comparison Bar Chart across all 3 references
st.markdown("##### Three-Way Performance Benchmark")
fig_comp = go.Figure(
    data=[
        go.Bar(
            name="Feasible Naive Baseline",
            x=["Fuel (t HFO-eq)", "Cost ($M)", "Emissions (kt CO2e)", "CI (g/t-nm)"],
            y=[
                naive["fuel_t"],
                naive["cost_usd"] / 1e6,
                naive["emissions_t"] / 1e3,
                naive["ci_g_tnm"],
            ],
            marker_color="#94a3b8",
        ),
        go.Bar(
            name="Best Conventional Baseline",
            x=["Fuel (t HFO-eq)", "Cost ($M)", "Emissions (kt CO2e)", "CI (g/t-nm)"],
            y=[
                best_conv["fuel_t"],
                best_conv["cost_usd"] / 1e6,
                best_conv["emissions_t"] / 1e3,
                best_conv["ci_g_tnm"],
            ],
            marker_color="#3b82f6",
        ),
        go.Bar(
            name="Multi-Objective Optimized Plan",
            x=["Fuel (t HFO-eq)", "Cost ($M)", "Emissions (kt CO2e)", "CI (g/t-nm)"],
            y=[
                opt["fuel_t"],
                opt["cost_usd"] / 1e6,
                opt["emissions_t"] / 1e3,
                opt["ci_g_tnm"],
            ],
            marker_color="#059669",
        ),
    ]
)
fig_comp.update_layout(barmode="group", template="plotly_white", height=360)
st.plotly_chart(fig_comp, width="stretch")

# 2. Route Allocation Details (with oversupply ratios)
st.markdown("---")
st.subheader("2. Corridor-by-Corridor Fleet Deployment Table")
st.markdown("Detailed route deployment parameters, including speed choices, vessel allocations, and **oversupply ratios** (capacity / demand).")
st.dataframe(df_routes, width="stretch")

# 3. 12-Month Simulated Operation
st.markdown("---")
st.subheader("3. 12-Month Simulated Operational Trajectory")
st.markdown("Simulates seasonal weather sensitivity across the Indian Ocean (monsoon peaks in June-August with weather multiplier up to 1.65x):")

fig_line = go.Figure()
fig_line.add_trace(
    go.Scatter(
        x=df_monthly["Month"],
        y=df_monthly["Naive CO2e (kt)"],
        mode="lines+markers",
        name="Naive Baseline CO2e (kt)",
        line=dict(color="#ef4444", dash="dash"),
    )
)
fig_line.add_trace(
    go.Scatter(
        x=df_monthly["Month"],
        y=df_monthly["Best Conv CO2e (kt)"],
        mode="lines+markers",
        name="Best Conv CO2e (kt)",
        line=dict(color="#3b82f6", dash="dot"),
    )
)
fig_line.add_trace(
    go.Scatter(
        x=df_monthly["Month"],
        y=df_monthly["Optimized CO2e (kt)"],
        mode="lines+markers",
        name="Optimized CO2e (kt)",
        line=dict(color="#10b981", width=3),
    )
)
fig_line.update_layout(
    xaxis_title="Month",
    yaxis_title="Monthly Lifecycle Emissions (kt CO2e)",
    template="plotly_white",
    height=360,
)
st.plotly_chart(fig_line, width="stretch")

# 4. Report Generation & Export
st.markdown("---")
st.subheader("4. Executive Report Export")
st.markdown("Generate and download a self-contained executive report or tabular CSV dataset:")

html_report_text = generate_html_report(case_data)
csv_dataset_text = generate_csv_summary(case_data)

rep_col1, rep_col2 = st.columns(2)

with rep_col1:
    st.download_button(
        label="📄 Download Executive HTML Report",
        data=html_report_text,
        file_name="green_fleet_case_study_report.html",
        mime="text/html",
        type="primary",
        width="stretch",
    )
    st.caption("Self-contained HTML report with responsive styling, KPI badges, operational tables, and synthetic disclaimer.")

with rep_col2:
    st.download_button(
        label="📊 Download Results CSV Dataset",
        data=csv_dataset_text,
        file_name="green_fleet_case_study_data.csv",
        mime="text/csv",
        width="stretch",
    )
    st.caption("Raw tabular CSV containing dual-baseline vs optimized route allocations, speeds, costs, emissions, and oversupply ratios.")
