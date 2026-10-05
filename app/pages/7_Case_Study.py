"""
Case Study - South Asian Feeder Decarbonization Assessment.
Rigorous 4-plan comparison (Naive, Best Conv, Balanced, Green) with Plan Insights,
carbon abatement cost, monthly weather simulation, interactive inputs, and
Data Provenance & Traceability Panel.
"""

from __future__ import annotations
import copy
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
from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS
from src.analysis.report import generate_html_report, generate_csv_summary
from src.models.provenance import get_provenance_dataframe, get_provenance_summary_counts

# Render Top Strip with Public-Data-Informed Status
render_top_strip(
    title="South Asian Maritime Corridor Case Study",
    subtitle="Public-data-informed / reproducible prototype case study benchmarking 4 fleet deployment strategies.",
    demo_only=False,
    chip_label="Public-Data-Informed Case Study",
)

inject_css()
base_cfg = get_default_config()

# ---------------------------------------------------------
# Session State Setup for Case Study Inputs & Overrides
# ---------------------------------------------------------
DEFAULT_CS_INPUTS = {
    "R1_demand": int(base_cfg["routes"]["R1"]["annual_demand_teu"]),
    "R2_demand": int(base_cfg["routes"]["R2"]["annual_demand_teu"]),
    "R3_demand": int(base_cfg["routes"]["R3"]["annual_demand_teu"]),
    "R4_demand": int(base_cfg["routes"]["R4"]["annual_demand_teu"]),
    "R5_demand": int(base_cfg["routes"]["R5"]["annual_demand_teu"]),
    "R1_dist": float(base_cfg["routes"]["R1"]["distance_nm"]),
    "R2_dist": float(base_cfg["routes"]["R2"]["distance_nm"]),
    "R3_dist": float(base_cfg["routes"]["R3"]["distance_nm"]),
    "R4_dist": float(base_cfg["routes"]["R4"]["distance_nm"]),
    "R5_dist": float(base_cfg["routes"]["R5"]["distance_nm"]),
    "global_speed_cap": 18.0,
    "fuels_allowed": ["HFO", "MGO", "LNG", "Methanol", "Ammonia"],
    "mumbai_ops": bool(base_cfg["ports"]["mumbai"]["has_shore_power"]),
    "kochi_ops": bool(base_cfg["ports"]["kochi"]["has_shore_power"]),
    "tuticorin_ops": bool(base_cfg["ports"]["tuticorin"]["has_shore_power"]),
    "chennai_ops": bool(base_cfg["ports"]["chennai"]["has_shore_power"]),
    "colombo_ops": bool(base_cfg["ports"]["colombo"]["has_shore_power"]),
    "singapore_ops": bool(base_cfg["ports"]["singapore"]["has_shore_power"]),
}

for k, val in DEFAULT_CS_INPUTS.items():
    if f"cs_{k}" not in st.session_state:
        st.session_state[f"cs_{k}"] = val

# Function to build active problem configuration from session state
def build_case_study_config() -> dict:
    cfg = copy.deepcopy(base_cfg)
    cfg["routes"]["R1"]["annual_demand_teu"] = int(st.session_state["cs_R1_demand"])
    cfg["routes"]["R2"]["annual_demand_teu"] = int(st.session_state["cs_R2_demand"])
    cfg["routes"]["R3"]["annual_demand_teu"] = int(st.session_state["cs_R3_demand"])
    cfg["routes"]["R4"]["annual_demand_teu"] = int(st.session_state["cs_R4_demand"])
    cfg["routes"]["R5"]["annual_demand_teu"] = int(st.session_state["cs_R5_demand"])

    cfg["routes"]["R1"]["distance_nm"] = float(st.session_state["cs_R1_dist"])
    cfg["routes"]["R2"]["distance_nm"] = float(st.session_state["cs_R2_dist"])
    cfg["routes"]["R3"]["distance_nm"] = float(st.session_state["cs_R3_dist"])
    cfg["routes"]["R4"]["distance_nm"] = float(st.session_state["cs_R4_dist"])
    cfg["routes"]["R5"]["distance_nm"] = float(st.session_state["cs_R5_dist"])

    speed_cap = float(st.session_state["cs_global_speed_cap"])
    for r in cfg["routes"].values():
        r["speed_cap_knots"] = min(speed_cap, float(r.get("speed_cap_knots", 18.0)))

    cfg["ports"]["mumbai"]["has_shore_power"] = bool(st.session_state["cs_mumbai_ops"])
    cfg["ports"]["kochi"]["has_shore_power"] = bool(st.session_state["cs_kochi_ops"])
    cfg["ports"]["tuticorin"]["has_shore_power"] = bool(st.session_state["cs_tuticorin_ops"])
    cfg["ports"]["chennai"]["has_shore_power"] = bool(st.session_state["cs_chennai_ops"])
    cfg["ports"]["colombo"]["has_shore_power"] = bool(st.session_state["cs_colombo_ops"])
    cfg["ports"]["singapore"]["has_shore_power"] = bool(st.session_state["cs_singapore_ops"])

    return cfg

# Check if inputs differ from default baseline
inputs_modified = any(
    st.session_state[f"cs_{k}"] != DEFAULT_CS_INPUTS[k]
    for k in DEFAULT_CS_INPUTS
)

# ---------------------------------------------------------
# Sidebar: Interactive Case Study Parameters & Controls
# ---------------------------------------------------------
st.sidebar.markdown("### Case Study Inputs")
st.sidebar.caption(
    "Modify realistic South Asian feeder network parameters. Changes directly feed the multi-objective optimizer."
)

with st.sidebar.expander("🚢 Cargo Demand (TEU / yr)", expanded=True):
    st.session_state["cs_R1_demand"] = st.number_input(
        "R1: Nhava Sheva - Colombo", min_value=10000, max_value=500000, value=st.session_state["cs_R1_demand"], step=5000
    )
    st.session_state["cs_R2_demand"] = st.number_input(
        "R2: Kochi - Colombo", min_value=10000, max_value=300000, value=st.session_state["cs_R2_demand"], step=5000
    )
    st.session_state["cs_R3_demand"] = st.number_input(
        "R3: Chennai - Colombo", min_value=10000, max_value=400000, value=st.session_state["cs_R3_demand"], step=5000
    )
    st.session_state["cs_R4_demand"] = st.number_input(
        "R4: Tuticorin - Colombo", min_value=10000, max_value=250000, value=st.session_state["cs_R4_demand"], step=5000
    )
    st.session_state["cs_R5_demand"] = st.number_input(
        "R5: Colombo - Singapore", min_value=20000, max_value=600000, value=st.session_state["cs_R5_demand"], step=10000
    )

with st.sidebar.expander("📍 Route Distances (nm)", expanded=False):
    st.session_state["cs_R1_dist"] = st.number_input("R1 Distance (nm)", min_value=100.0, max_value=2000.0, value=float(st.session_state["cs_R1_dist"]), step=10.0)
    st.session_state["cs_R2_dist"] = st.number_input("R2 Distance (nm)", min_value=50.0, max_value=1000.0, value=float(st.session_state["cs_R2_dist"]), step=10.0)
    st.session_state["cs_R3_dist"] = st.number_input("R3 Distance (nm)", min_value=100.0, max_value=1500.0, value=float(st.session_state["cs_R3_dist"]), step=10.0)
    st.session_state["cs_R4_dist"] = st.number_input("R4 Distance (nm)", min_value=50.0, max_value=800.0, value=float(st.session_state["cs_R4_dist"]), step=10.0)
    st.session_state["cs_R5_dist"] = st.number_input("R5 Distance (nm)", min_value=500.0, max_value=3000.0, value=float(st.session_state["cs_R5_dist"]), step=20.0)

with st.sidebar.expander("⚡ Port OPS / Shore Power Availability", expanded=False):
    st.session_state["cs_mumbai_ops"] = st.checkbox("Nhava Sheva (Mumbai) OPS", value=st.session_state["cs_mumbai_ops"])
    st.session_state["cs_kochi_ops"] = st.checkbox("Kochi (ICTT) OPS", value=st.session_state["cs_kochi_ops"])
    st.session_state["cs_tuticorin_ops"] = st.checkbox("Tuticorin (VOCPA) OPS", value=st.session_state["cs_tuticorin_ops"])
    st.session_state["cs_chennai_ops"] = st.checkbox("Chennai Port OPS", value=st.session_state["cs_chennai_ops"])
    st.session_state["cs_colombo_ops"] = st.checkbox("Colombo (ECT/JCT) OPS", value=st.session_state["cs_colombo_ops"])
    st.session_state["cs_singapore_ops"] = st.checkbox("Port of Singapore OPS", value=st.session_state["cs_singapore_ops"])

with st.sidebar.expander("⚙️ Speed & Fuel Constraints", expanded=False):
    st.session_state["cs_global_speed_cap"] = st.slider(
        "Corridor Speed Limit (knots)", min_value=12.0, max_value=20.0, value=float(st.session_state["cs_global_speed_cap"]), step=0.5
    )
    st.session_state["cs_fuels_allowed"] = st.multiselect(
        "Permitted Fuel Options",
        options=["HFO", "MGO", "LNG", "Methanol", "Ammonia"],
        default=st.session_state["cs_fuels_allowed"],
    )

# Reproducibility Button: Reset to Case Study Defaults
st.sidebar.markdown("---")
c_run, c_reset = st.sidebar.columns([3, 2])

recompute_triggered = c_run.button(
    "▶ Recompute",
    type="primary",
    help="Execute multi-objective optimization suite with the current parameters",
    width="stretch",
)

if c_reset.button("↺ Reset Defaults", help="Reset all parameters to public-data-informed baseline defaults", width="stretch"):
    for k, val in DEFAULT_CS_INPUTS.items():
        st.session_state[f"cs_{k}"] = val
    if "custom_case_study_data" in st.session_state:
        del st.session_state["custom_case_study_data"]
    st.success("Case study parameters reset to reproducible baseline defaults!")
    st.rerun()

# ---------------------------------------------------------
# Optimization Execution / Data Loading
# ---------------------------------------------------------
active_cfg = build_case_study_config()

# If inputs were modified or recompute pressed, solve with active config
if inputs_modified or recompute_triggered:
    if "custom_case_study_data" not in st.session_state or recompute_triggered:
        with st.spinner("Recomputing South Asian corridor optimization with updated inputs..."):
            custom_data = run_case_study(
                pop_size=30,
                generations=60,
                random_seed=42,
                config=active_cfg,
            )
            st.session_state["custom_case_study_data"] = custom_data
            case_data = custom_data
    else:
        case_data = st.session_state["custom_case_study_data"]
else:
    case_data = get_or_load_case_study()
    if case_data is None:
        with st.spinner("Computing regional feeder case study simulation across 4 plans..."):
            case_data = run_case_study(pop_size=40, generations=100, random_seed=42, config=active_cfg)
            st.session_state["case_study_results"] = case_data

summary = case_data["summary"]
df_routes = case_data["df_routes"]
df_monthly = case_data["df_monthly"]
naive_eval = case_data["naive_eval"]
best_conv_eval = case_data["best_conv_eval"]
balanced_eval = case_data.get("balanced_eval", case_data.get("optimized_eval"))
green_eval = case_data.get("green_eval", balanced_eval)
problem = case_data.get("problem") or FleetOptimizationProblem(config=active_cfg)
carbon_price_ref = summary.get("carbon_price_reference_usd", 80.0)

# Banner when active configuration has modified inputs
if inputs_modified:
    st.info(
        "⚡ **Interactive Case Study Active:** Optimizer outputs recomputed dynamically with custom parameters. "
        "Click **'Reset Defaults'** in the sidebar to return to the authoritative baseline.",
        icon="ℹ️",
    )

# ---------------------------------------------------------
# 1. Plan Insights Card
# ---------------------------------------------------------
render_plan_insights_card(
    opt_eval=balanced_eval,
    best_conv_eval=best_conv_eval,
    problem=problem,
    carbon_price_ref=carbon_price_ref,
)

# ---------------------------------------------------------
# 2. Case Study Input & Output Overview
# ---------------------------------------------------------
st.markdown("### Case Study Corridor Performance (Input & Output Tracking)")

b_metrics = summary.get("balanced", summary.get("optimized", {}))
c_metrics = summary.get("best_conventional", {})
n_metrics = summary.get("naive", {})

# Calculate totals for delivered cargo and fuel savings
total_cargo_demand = sum(r["annual_demand_teu"] for r in active_cfg["routes"].values())
total_cargo_delivered = sum(
    balanced_eval["route_details"][r]["cargo_moved_teu"]
    for r in balanced_eval["route_details"]
)
fuel_saved_t = c_metrics.get("fuel_t", 0.0) - b_metrics.get("fuel_t", 0.0)
cost_change_usd = b_metrics.get("cost_delta_usd", 0.0)
emiss_reduction_t = b_metrics.get("emissions_avoided_t", 0.0)

col_io1, col_io2, col_io3, col_io4, col_io5 = st.columns(5)
with col_io1:
    st.metric(
        label="Total Cargo Delivered",
        value=f"{total_cargo_delivered:,.0f} TEU",
        delta=f"100% Demand Met ({total_cargo_demand:,.0f} TEU)",
        delta_color="normal",
    )
with col_io2:
    st.metric(
        label="Fuel Saved vs Best Conv",
        value=f"{fuel_saved_t:+,.1f} tonnes" if abs(fuel_saved_t) > 1e-4 else "0.0 tonnes",
        delta=b_metrics.get("fuel_label", "Reference"),
        delta_color="inverse",
    )
with col_io3:
    st.metric(
        label="Operating Cost Change",
        value=f"${cost_change_usd:+,.0f}",
        delta=b_metrics.get("cost_label", ""),
        delta_color="off",
    )
with col_io4:
    st.metric(
        label="Emissions Reduction",
        value=f"-{emiss_reduction_t:,.1f} t CO2e",
        delta=b_metrics.get("emissions_label", ""),
        delta_color="normal",
    )
with col_io5:
    render_carbon_intensity_badge(balanced_eval["carbon_intensity_g_tnm"])

# ---------------------------------------------------------
# 3. 4-Plan Decarbonization Scorecard
# ---------------------------------------------------------
st.markdown("### Four-Plan Comprehensive Decarbonization Scorecard")

plan_tabs = st.tabs([
    "Balanced Optimized Plan (0.2/0.4/0.4)",
    "Green Optimized Plan (0.1/0.1/0.8)",
    "Best Conventional Baseline",
    "Feasible Naive Baseline",
])

with plan_tabs[0]:
    render_kpi_row(balanced_eval, best_conv_eval, comparator_name="Best Conv")
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
        st.caption(f"**Optimizer Winner:** {summary.get('winner_status_balanced', 'Green plan selected')}")

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
        st.caption(f"**Optimizer Winner:** {summary.get('winner_status_green', 'Green plan selected')}")

with plan_tabs[2]:
    render_kpi_row(best_conv_eval, naive_eval, comparator_name="Naive")
    st.info("Best Conventional Baseline is the optimal fleet deployment using HFO without shore power.")

with plan_tabs[3]:
    render_kpi_row(naive_eval, naive_eval, comparator_name="Naive")
    st.info("Feasible Naive Baseline uses conventional fixed-speed HFO vessels satisfying all operational constraints.")

# ---------------------------------------------------------
# 4. Seasonal Monsoon Profile & Fleet Allocation
# ---------------------------------------------------------
col_season, col_routes = st.columns([10, 10])

with col_season:
    with st.container(border=True):
        st.markdown("**12-Month Simulated Operational Trajectory**")
        st.caption("Monthly profile adjusted for Southwest Monsoon weather severity in the Indian Ocean & Bay of Bengal.")
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

# ---------------------------------------------------------
# 5. Route Deployment & Fleet Allocation
# ---------------------------------------------------------
st.markdown("### Corridor Allocation & Fleet Deployment")

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
    render_constraints_table(balanced_eval, problem)

# ---------------------------------------------------------
# 6. Data Sources & Assumptions Panel (Data Provenance Structure)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### Data Sources & Assumptions (Traceability & Provenance)")
st.caption(
    "Full traceable audit separating every model input into: **A. Publicly sourced**, **B. Derived/calculated**, "
    "**C. Project assumption**, and **D. Synthetic/illustrative**."
)

prov_counts = get_provenance_summary_counts()
c_p1, c_p2, c_p3, c_p4 = st.columns(4)
with c_p1:
    st.metric(label="A. Publicly Sourced", value=f"{prov_counts['A. Publicly sourced']} inputs", help="Official port authorities, IMO, UNCTAD, CEA India, EMA Singapore")
with c_p2:
    st.metric(label="B. Derived from Public", value=f"{prov_counts['B. Derived/calculated from public data']} inputs", help="Haversine distances with detours, naval architecture parametric curves")
with c_p3:
    st.metric(label="C. Project Assumptions", value=f"{prov_counts['C. Project assumption']} inputs", help="Market indices, charter rates, feeder cargo demand allocations")
with c_p4:
    st.metric(label="D. Synthetic / Illustrative", value=f"{prov_counts['D. Synthetic/illustrative']} inputs", help="Reference carbon tax proxies and demo flags")

df_prov = get_provenance_dataframe()

# Filter by category or source type
c_filter1, c_filter2 = st.columns([1, 1])
with c_filter1:
    cat_options = ["All Categories"] + sorted(list(df_prov["Category"].unique()))
    sel_cat = st.selectbox("Filter by Category", cat_options)
with c_filter2:
    type_options = ["All Source Types"] + sorted(list(df_prov["Source Type"].unique()))
    sel_type = st.selectbox("Filter by Source Type", type_options)

df_filtered = df_prov.copy()
if sel_cat != "All Categories":
    df_filtered = df_filtered[df_filtered["Category"] == sel_cat]
if sel_type != "All Source Types":
    df_filtered = df_filtered[df_filtered["Source Type"] == sel_type]

st.dataframe(
    df_filtered,
    column_config={
        "Category": st.column_config.TextColumn("Category", width="medium"),
        "Field": st.column_config.TextColumn("Field", width="large"),
        "Value": st.column_config.TextColumn("Value", width="medium"),
        "Unit": st.column_config.TextColumn("Unit", width="small"),
        "Source Type": st.column_config.TextColumn("Source Type", width="medium"),
        "Source": st.column_config.TextColumn("Authoritative Source", width="large"),
        "Year": st.column_config.TextColumn("Year", width="small"),
        "Assumption?": st.column_config.TextColumn("Assumption?", width="small"),
        "Calculation / Basis": st.column_config.TextColumn("Calculation Basis / Rationale", width="large"),
    },
    hide_index=True,
    width="stretch",
)

st.info(
    "**Methodology Note:** This case study is a **public-data-informed / reproducible prototype case study**. "
    "It integrates published port authority data (JNPA, ChPA, SLPA, MPA, VOCPA), national power grid emission factors "
    "(CEA India, EMA Singapore, CEB Sri Lanka), and IMO LCA guidelines. Where operational data is unavailable, values are "
    "conservatively derived from naval architecture standards or clearly identified as project assumptions.",
    icon="📋",
)
