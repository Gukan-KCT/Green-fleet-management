"""
Fleet Planner - Main Decision-Support Workspace.
Interactive multi-objective fleet deployment, alternative fuels, and decarbonization engine.
Includes Plan Insights card, interactive Pareto trade-off with knee point,
and simplified carbon intensity proxy.
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
    render_plan_insights_card,
    render_carbon_intensity_badge,
)
from app.ui.charts import (
    build_network_map,
    build_allocation_stacked_bar,
    build_emissions_breakdown_chart,
    build_cost_breakdown_chart,
    build_convergence_chart,
    build_pareto_chart,
)
from app.ui.state import get_or_load_plan, get_default_config, check_artifact_staleness
from app.ui.css import inject_css
from src.models.network import get_demo_network
from src.optimization.pareto import generate_pareto_frontier
from src.analysis.decision_support import compute_pareto_knee_point
from src.analysis.report import generate_standalone_html_report


inject_css()

# --- 1. Top Strip & Header ---
render_top_strip(
    title="Fleet Planner",
    subtitle="Configure constraints and optimize fleet assignment across regional shipping corridors.",
)

cfg = get_default_config()

# Guided Demo Flow & Presets
c_flow, c_dl = st.columns([4, 1])
with c_flow:
    st.caption("**Guided Workflow:** 1. Select Preset / Baseline &rarr; 2. Adjust Constraints &rarr; 3. Run Optimization &rarr; 4. Explore Trade-offs")
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

# --- 2. Simplified Sidebar (Max 5 Visible Controls, Measured by Audit) ---
st.sidebar.markdown("### Plan Configuration")

# Active Network Status & Switcher Link
active_net = st.session_state.get("active_network", get_demo_network())
is_demo = getattr(active_net, "is_demo", True)
net_name = active_net.name if hasattr(active_net, "name") else "Demo Network"
num_routes = len(active_net.routes) if hasattr(active_net, "routes") else 5

c_net_info, c_net_btn = st.sidebar.columns([3, 2])
with c_net_info:
    st.caption(f"**Network:** {net_name} ({num_routes} routes)")
with c_net_btn:
    if st.button("✏ Edit", help="Open Network Builder to customize ports & routes", width="stretch"):
        st.switch_page("pages/1_Network.py")

# Control 1: Primary Objective Selector
obj_options = [
    "Balanced Decarbonization",
    "Lowest Operating Cost",
    "Lowest Lifecycle CO2e",
    "Lowest Fuel Consumption",
]
selected_obj = st.sidebar.selectbox(
    "Optimization Objective",
    options=obj_options,
    index=0,
    help="Primary strategic objective for fleet vessel assignment and cruising speeds.",
)

# Map Macro Objective to Normalized Weights
if selected_obj == "Balanced Decarbonization":
    default_w = (0.20, 0.40, 0.40)
elif selected_obj == "Lowest Operating Cost":
    default_w = (0.10, 0.80, 0.10)
elif selected_obj == "Lowest Lifecycle CO2e":
    default_w = (0.10, 0.10, 0.80)
elif selected_obj == "Lowest Fuel Consumption":
    default_w = (0.80, 0.10, 0.10)
else:
    default_w = (0.20, 0.40, 0.40)

# Control 2: Allowed Marine Fuels with Merged Conditional Pathway
all_fuel_names = ["HFO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
allowed_fuels_sel = st.sidebar.multiselect(
    "Allowed Marine Fuels",
    options=all_fuel_names,
    default=all_fuel_names,
    help="Filter vessel candidate pool by permissible fuel systems.",
)

# Conditional Fuel Pathway Selector (appears only when synthetic/alternative fuels are enabled)
selected_pathway = "green"
has_alt_fuels = any(f in allowed_fuels_sel for f in ["Methanol", "Ammonia", "Hydrogen"])
if has_alt_fuels:
    selected_pathway = st.sidebar.selectbox(
        "Alternative Fuel Pathway",
        options=["green", "blue", "grey"],
        index=0,
        format_func=lambda x: f"{x.title()} Pathway ({'Renewable e-fuel' if x=='green' else 'Fossil with CCS' if x=='blue' else 'Fossil baseline'})",
        help="Upstream production carbon accounting methodology.",
    )

# Control 3: Shore Power Toggle
shore_power_toggle = st.sidebar.checkbox(
    "Enable Port Shore Power (Cold Ironing)",
    value=True,
    help="Allow vessels equipped with shore connections to connect at equipped berths.",
)

# --- Collapsed Expander 1: Fine-Tune Objectives ---
with st.sidebar.expander("Fine-Tune Objectives (Weights)", expanded=False):
    w_fuel_in = st.slider("Fuel Weight", 0, 100, int(default_w[0] * 100), key="w_f_slider")
    w_cost_in = st.slider("Cost Weight", 0, 100, int(default_w[1] * 100), key="w_c_slider")
    w_emiss_in = st.slider("Emissions Weight", 0, 100, int(default_w[2] * 100), key="w_e_slider")
    w_total = max(1e-6, w_fuel_in + w_cost_in + w_emiss_in)
    w_fuel = round(w_fuel_in / w_total, 3)
    w_cost = round(w_cost_in / w_total, 3)
    w_emiss = round(1.0 - w_fuel - w_cost, 3)
    st.caption(f"Normalized: Fuel **{w_fuel:.2f}** | Cost **{w_cost:.2f}** | CO2e **{w_emiss:.2f}**")

# --- Collapsed Expander 2: What-If Adjustments ---
with st.sidebar.expander("What-If Adjustments", expanded=False):
    speed_cap = st.slider("Fleet Speed Cap (knots)", 12.0, 22.0, 18.0, 0.5, help="Approximate corridor speed limit.")
    fuel_price_mult = st.slider("Fuel Price Multiplier", 0.5, 2.5, 1.0, 0.1, help="Stress test fuel price spikes.")
    demand_mult = st.slider("Demand Multiplier", 0.5, 2.0, 1.0, 0.1, help="Scale corridor cargo demand.")

# --- Collapsed Expander 3: Advanced Optimization Settings ---
with st.sidebar.expander("Advanced Optimization", expanded=False):
    search_effort = st.selectbox(
        "Search Effort Budget",
        options=["Quick (5k evals)", "Standard (20k evals)", "Thorough (50k evals)"],
        index=1,
        help="Controls number of unseeded QIEA multi-starts and evaluations.",
    )
    if "Quick" in search_effort:
        num_starts, evals_per_start = 3, 1700
    elif "Thorough" in search_effort:
        num_starts, evals_per_start = 5, 10000
    else:
        num_starts, evals_per_start = 5, 4000

    rand_seed = st.number_input("Random Seed", min_value=1, max_value=9999, value=42)

# Action Row: Primary Run & Reset Buttons
col_btn1, col_btn2 = st.sidebar.columns([3, 2])
run_clicked = col_btn1.button("Run optimization", type="primary", width="stretch")
reset_clicked = col_btn2.button("Reset", width="stretch")

if reset_clicked:
    for k in list(st.session_state.keys()):
        if k.startswith("current_plan_result"):
            st.session_state.pop(k, None)
    st.query_params.clear()
    st.rerun()


# --- 3. Compute or Retrieve Optimization Plan ---
with st.spinner("Evaluating multi-objective fleet configuration..."):
    plan = get_or_load_plan(
        weights=(w_fuel, w_cost, w_emiss),
        allowed_fuels=allowed_fuels_sel if len(allowed_fuels_sel) < 5 else None,
        shore_power=shore_power_toggle,
        speed_cap=speed_cap,
        force_recompute=run_clicked,
        random_seed=rand_seed,
        num_starts=num_starts,
        evals_per_start=evals_per_start,
    )

opt_eval = plan["optimized_eval"]
naive_eval = plan["naive_eval"]
best_conv_eval = plan["best_conv_eval"]
df_routes = plan["df_routes"]
problem = plan["problem"]

# Infeasibility Diagnostic Explainer (if constraints failed)
infeas_suggestions = plan.get("infeasibility_suggestions", [])
if not opt_eval.get("is_feasible", True) or infeas_suggestions:
    st.error("⚠️ **Infeasible Fleet Plan**: Operational or regulatory constraints could not be satisfied under these exact settings.")
    for s in infeas_suggestions:
        st.info(f"💡 **Constraint Analysis:** {s}")

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

# Staleness Notice Check (Applies to Demo Network Only)
if not plan.get("is_custom_network", False):
    if check_artifact_staleness("saved_case_study.pkl"):
        st.warning("Saved results are out of date, press Re-run to update.", icon="⚠️")
else:
    st.info("ℹ️ **Active Custom Network**: Results dynamically computed in real-time. Precomputed cache bypassed.", icon="🌐")

# Plan Selection Status & Carbon Intensity Rating Badge
c_stat1, c_stat2 = st.columns([13, 7])
with c_stat1:
    winner_status = plan.get("winner_status", "Green plan selected")
    if "Green plan selected" in winner_status:
        st.success(f"**{winner_status}**: Multi-objective QIEA search identified a decarbonized fleet configuration dominating conventional operations.", icon="🌱")
    elif "Conventional plan retained" in winner_status:

        st.info(f"**{winner_status}**.", icon="ℹ️")
    else:
        st.info(f"**{winner_status}**.", icon="⚓")

with c_stat2:
    ci_val = opt_eval.get("carbon_intensity_g_tnm", 15.0)
    render_carbon_intensity_badge(ci_val)

# Plan Insights Card (Executive Data Summary)
carbon_price_ref = float(cfg.get("general", {}).get("carbon_price_usd_per_tonne", 80.0))
render_plan_insights_card(
    opt_eval=opt_eval,
    best_conv_eval=best_conv_eval,
    problem=problem,
    carbon_price_ref=carbon_price_ref,
)

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
    "Trade-Off Explorer (Pareto)",
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
    st.markdown("**Multi-Objective Trade-Off Explorer & Knee-Point Analysis**")
    st.caption("Evaluates the efficient frontier between Annual Operating Cost ($M) and Lifecycle CO2e (kt).")

    if "pareto_data" not in st.session_state:
        st.session_state["pareto_data"] = None

    c_p1, c_p2 = st.columns([3, 7])
    with c_p1:
        calc_pareto = st.button("Generate Frontier", type="primary", width="stretch")
    with c_p2:
        st.caption("Knee Point identifies the policy maximizing marginal emissions reduction per dollar spent (minimum Euclidean distance to ideal utopia point in normalized objective space).")

    if calc_pareto or st.session_state["pareto_data"] is not None:
        if calc_pareto or st.session_state["pareto_data"] is None:
            with st.spinner("Sweeping multi-objective trade-off frontier..."):
                df_pareto = generate_pareto_frontier(
                    problem=problem,
                    num_points=12,
                    pop_size=30,
                    generations=60,
                    random_seed=rand_seed,
                )
                st.session_state["pareto_data"] = df_pareto
        else:
            df_pareto = st.session_state["pareto_data"]

        knee_pt = compute_pareto_knee_point(df_pareto)
        fig_p = build_pareto_chart(
            pareto_df=df_pareto,
            naive_eval=naive_eval,
            best_conv_eval=best_conv_eval,
            knee_point=knee_pt,
        )
        st.plotly_chart(fig_p, width="stretch")

        if knee_pt:
            st.info(
                f"**Knee Point Policy Identified:** Operating Cost **${knee_pt['Operating Cost ($M)']:.2f}M**, "
                f"Lifecycle CO2e **{knee_pt['Lifecycle CO2e (kt)']:.2f} kt** "
                f"(Weights: Cost {knee_pt.get('w_cost', 0.5):.2f}, CO2e {knee_pt.get('w_emiss', 0.5):.2f})."
            )
    else:
        st.info("Click 'Generate Frontier' to evaluate the non-dominated Pareto frontier.")
