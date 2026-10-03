"""
Fleet Planner - Main Decision-Support Workspace.
Interactive multi-objective fleet deployment, alternative fuels, and decarbonization engine.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# Set page config FIRST before any other Streamlit calls
st.set_page_config(
    page_title="Fleet Planner | Green Fleet",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import (
    render_top_strip,
    render_kpi_row,
    render_constraints_table,
    render_oversupply_chips,
)
from app.ui.charts import (
    build_network_map,
    build_allocation_stacked_bar,
    build_emissions_breakdown_chart,
    build_cost_breakdown_chart,
    build_convergence_chart,
    build_pareto_chart,
)
from app.ui.state import get_or_load_plan, get_default_config
from app.ui.css import inject_css
from src.optimization.pareto import generate_pareto_frontier
from src.analysis.report import generate_standalone_html_report

inject_css()

# --- 1. Top Strip & Header ---
render_top_strip(
    title="Fleet Planner",
    subtitle="Configure constraints and optimize fleet assignment across regional shipping corridors.",
)

cfg = get_default_config()

# Presets Bar
c_presets, c_dl = st.columns([4, 1])
with c_presets:
    p_cols = st.columns(6)
    preset_clicked = None
    if p_cols[0].button("Balanced", help="Equal focus on cost and emissions (0.2/0.4/0.4)", width="stretch"):
        preset_clicked = "balanced"
    if p_cols[1].button("Min Cost", help="Prioritize low operational expenditure (0.1/0.8/0.1)", width="stretch"):
        preset_clicked = "min_cost"
    if p_cols[2].button("Min CO2e", help="Aggressive decarbonization (0.1/0.1/0.8)", width="stretch"):
        preset_clicked = "min_emiss"
    if p_cols[3].button("Min Fuel", help="Minimize bunker consumption (0.8/0.1/0.1)", width="stretch"):
        preset_clicked = "min_fuel"
    if p_cols[4].button("Fuel Surge", help="Stress test $1,200/t bunker price", width="stretch"):
        preset_clicked = "fuel_surge"
    if p_cols[5].button("Demand +20%", help="Surge demand +20% on all corridors", width="stretch"):
        preset_clicked = "demand_surge"

# --- 2. Sidebar Plan Settings ---
st.sidebar.markdown("### Plan Settings")

# Handle Presets in Session State
if preset_clicked == "balanced":
    st.session_state["w_fuel_raw"] = 20
    st.session_state["w_cost_raw"] = 40
    st.session_state["w_emiss_raw"] = 40
elif preset_clicked == "min_cost":
    st.session_state["w_fuel_raw"] = 10
    st.session_state["w_cost_raw"] = 80
    st.session_state["w_emiss_raw"] = 10
elif preset_clicked == "min_emiss":
    st.session_state["w_fuel_raw"] = 10
    st.session_state["w_cost_raw"] = 10
    st.session_state["w_emiss_raw"] = 80
elif preset_clicked == "min_fuel":
    st.session_state["w_fuel_raw"] = 80
    st.session_state["w_cost_raw"] = 10
    st.session_state["w_emiss_raw"] = 10

st.sidebar.caption("**Objective Priorities** (auto-normalized to 1.0)")
w_fuel_in = st.sidebar.slider(
    "Fuel Weight", 0, 100, st.session_state.get("w_fuel_raw", 20), key="w_fuel_slider",
    help="Relative priority for minimizing bunker fuel consumption.",
)
w_cost_in = st.sidebar.slider(
    "Cost Weight", 0, 100, st.session_state.get("w_cost_raw", 40), key="w_cost_slider",
    help="Relative priority for minimizing OPEX (bunker, charter, fees, carbon tax).",
)
w_emiss_in = st.sidebar.slider(
    "Emissions Weight", 0, 100, st.session_state.get("w_emiss_raw", 40), key="w_emiss_slider",
    help="Relative priority for minimizing Well-to-Wake lifecycle emissions.",
)

# Auto-normalize weights
w_total = max(1e-6, w_fuel_in + w_cost_in + w_emiss_in)
w_fuel = round(w_fuel_in / w_total, 3)
w_cost = round(w_cost_in / w_total, 3)
w_emiss = round(1.0 - w_fuel - w_cost, 3)
st.sidebar.caption(f"Normalized: Fuel **{w_fuel:.2f}** | Cost **{w_cost:.2f}** | CO2e **{w_emiss:.2f}**")

st.sidebar.markdown("---")
st.sidebar.caption("**Fleet & Fuel Capabilities**")
all_fuel_names = ["HFO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
allowed_fuels_sel = st.sidebar.multiselect(
    "Allowed Marine Fuels",
    options=all_fuel_names,
    default=all_fuel_names,
    help="Filter vessel options by permissible bunker fuel systems.",
)

shore_power_toggle = st.sidebar.checkbox(
    "Enable Port Shore Power",
    value=True,
    help="Allow vessels equipped with shore connections to cold-iron at equipped berths.",
)

speed_cap = st.sidebar.slider(
    "Fleet Speed Cap (knots)",
    min_value=12.0,
    max_value=22.0,
    value=18.0,
    step=0.5,
    help="Maximum operational cruising speed limit across corridors.",
)

with st.sidebar.expander("Advanced Optimization Parameters", expanded=False):
    rand_seed = st.number_input("Random Seed", min_value=1, max_value=9999, value=42)
    pop_size = st.slider("QIEA Population Size", min_value=20, max_value=80, value=40, step=5)
    generations = st.slider("Max Generations", min_value=50, max_value=300, value=150, step=25)

# Run & Reset Buttons
col_btn1, col_btn2 = st.sidebar.columns([3, 2])
run_clicked = col_btn1.button("Run optimization", type="primary", width="stretch")
reset_clicked = col_btn2.button("Reset", width="stretch")

if reset_clicked:
    st.session_state.pop("current_plan_result", None)
    st.session_state.pop("w_fuel_raw", None)
    st.session_state.pop("w_cost_raw", None)
    st.session_state.pop("w_emiss_raw", None)
    st.rerun()

# --- 3. Compute or Retrieve Optimization Plan ---
with st.spinner("Evaluating multi-objective fleet configuration..."):
    plan = get_or_load_plan(
        weights=(w_fuel, w_cost, w_emiss),
        allowed_fuels=allowed_fuels_sel if len(allowed_fuels_sel) < 5 else None,
        shore_power=shore_power_toggle,
        speed_cap=speed_cap,
        force_recompute=run_clicked,
        pop_size=pop_size,
        generations=generations,
        random_seed=rand_seed,
    )

opt_eval = plan["optimized_eval"]
naive_eval = plan["naive_eval"]
best_conv_eval = plan["best_conv_eval"]
df_routes = plan["df_routes"]
problem = plan["problem"]

# Report Download in Top Strip
with c_dl:
    report_html = generate_standalone_html_report(
        opt_eval=opt_eval,
        naive_eval=naive_eval,
        best_conv_eval=best_conv_eval,
        df_routes=df_routes,
    )
    st.download_button(
        label="Download report",
        data=report_html,
        file_name="green_fleet_optimization_report.html",
        mime="text/html",
        width="stretch",
    )

# Staleness Notice Check
from app.ui.state import check_artifact_staleness
if check_artifact_staleness("saved_case_study.pkl"):
    st.warning("Saved results are out of date, press Re-run to update.", icon="⚠️")

# Plan Selection Status
winner_status = plan.get("winner_status", "Green plan selected")
if "Green plan selected" in winner_status:
    st.success(f"**{winner_status}**: Multi-objective QIEA search identified a decarbonized fleet configuration dominating conventional operations.", icon="🌱")
elif "Conventional plan retained" in winner_status:
    st.info(f"**{winner_status}**.", icon="ℹ️")
else:
    st.info(f"**{winner_status}**.", icon="⚓")

# --- 4. Row 1: KPI Cards with Comparator Toggle ---
c_comp, _ = st.columns([3, 7])
with c_comp:
    comparator = st.radio(
        "Baseline Comparator:",
        options=["Feasible Naive Baseline", "Best Conventional Baseline"],
        horizontal=True,
        help="Compare the optimized multi-objective plan against either fixed-speed HFO or optimized HFO.",
    )

active_baseline = naive_eval if comparator == "Feasible Naive Baseline" else best_conv_eval
comp_label = "Naive" if comparator == "Feasible Naive Baseline" else "Best Conv"

render_kpi_row(opt_eval, active_baseline, comparator_name=comp_label)

# --- 5. Row 2: Network Map & Fleet Allocation ---
col_map, col_alloc = st.columns([11, 9])

with col_map:
    with st.container(border=True):
        st.markdown("**Regional Corridor Network Map**")
        st.caption("Thickness reflects vessel count; color reflects assigned bunker fuel.")
        fig_map = build_network_map(df_routes, cfg.get("ports", {}))
        st.plotly_chart(fig_map, width="stretch")

with col_alloc:
    with st.container(border=True):
        st.markdown("**Fleet Allocation by Corridor**")
        st.caption("Distribution of vessels and propulsion technologies per shipping lane.")
        fig_alloc = build_allocation_stacked_bar(df_routes)
        fig_alloc.layout.title = None
        st.plotly_chart(fig_alloc, width="stretch")

with st.expander("Detailed Route Deployment & Oversupply Metrics Table", expanded=False):
    st.dataframe(
        df_routes,
        column_config={
            "Route ID": st.column_config.TextColumn("Corridor"),
            "Vessels": st.column_config.NumberColumn("Vessels", format="%d"),
            "Speed (knots)": st.column_config.NumberColumn("Cruising Speed", format="%.1f kn"),
            "Capacity (TEU/yr)": st.column_config.NumberColumn("Route Cap", format="%d TEU"),
            "Demand (TEU/yr)": st.column_config.NumberColumn("Demand", format="%d TEU"),
            "Oversupply Ratio": st.column_config.NumberColumn("Oversupply", format="%.2fx"),
            "Reliability (%)": st.column_config.NumberColumn("Reliability", format="%.1f%%"),
            "Voyage Cost ($/yr)": st.column_config.NumberColumn("Annual Cost", format="$%d"),
            "Lifecycle CO2e (t/yr)": st.column_config.NumberColumn("CO2e", format="%d t"),
        },
        hide_index=True,
        width="stretch",
    )

# --- 6. Row 3: Analytical Tabs ---
tab_emiss, tab_cost, tab_const, tab_conv, tab_pareto = st.tabs([
    "Emissions Breakdown",
    "Cost Breakdown",
    "Constraints & Oversupply",
    "Convergence",
    "Pareto Front",
])

with tab_emiss:
    fig_emiss = build_emissions_breakdown_chart(opt_eval)
    st.plotly_chart(fig_emiss, width="stretch")

with tab_cost:
    fig_cost = build_cost_breakdown_chart(opt_eval)
    st.plotly_chart(fig_cost, width="stretch")

with tab_const:
    st.markdown("**Regulatory & Operational Constraint Audit**")
    st.caption("Verifies vessel fleet availability, annual cargo demand, service frequency, and speed envelopes.")
    render_constraints_table(opt_eval, problem)

    st.markdown("**Route Oversupply Ratios (Capacity / Demand)**")
    st.caption("Monitors vessel slot utilization to prevent excessive non-productive capacity deployment.")
    render_oversupply_chips(opt_eval)

with tab_conv:
    fig_conv = build_convergence_chart(plan["convergence"])
    st.plotly_chart(fig_conv, width="stretch")

with tab_pareto:
    st.caption("Generates non-dominated frontier across 15 weighted cost-vs-emission evaluations.")
    if st.button("Generate Pareto Frontier"):
        with st.spinner("Sweeping multi-objective trade-off weights..."):
            df_pareto = generate_pareto_frontier(
                problem=problem,
                num_points=12,
                pop_size=30,
                generations=60,
                random_seed=rand_seed,
            )
            fig_p = build_pareto_chart(df_pareto)
            st.plotly_chart(fig_p, width="stretch")
    else:
        st.info("Click above to compute live Pareto front across cost and emission objectives.")
