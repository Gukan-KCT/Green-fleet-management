"""
Scenarios - Policy, Economic, and Climate Stress-Testing Workspace.
Compare fleet allocations across carbon taxes, weather contingencies, demand booms,
and interactive break-even carbon price sensitivity heatmaps.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Scenarios | Green Fleet",
    page_icon="🔮",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, UI_COLORS, FUEL_COLORS, get_fuel_color
from app.ui.charts import build_breakeven_heatmap
from app.ui.css import inject_css
from app.ui.state import get_default_config, get_or_load_breakeven_grid, check_artifact_staleness
from src.analysis.scenarios import (
    PRESET_SCENARIOS,
    evaluate_scenario,
    run_all_preset_scenarios,
)

render_top_strip(
    title="Scenario Manager & Break-Even Analysis",
    subtitle="Simulate market shocks, weather contingencies, and 2D carbon tax sensitivity heatmaps.",
)

inject_css()
cfg = get_default_config()

if check_artifact_staleness("saved_breakeven_grid.pkl"):
    st.warning("Saved scenario & break-even results are out of date, press Re-run to update.", icon="⚠️")

# Main Page Tabs
scen_tab1, scen_tab2 = st.tabs([
    "Scenario Stress Testing",
    "Break-Even Carbon Price Heatmap",
])

with scen_tab1:
    # --- 1. Scenario Selection & Custom Builder ---
    c_sel, c_custom = st.columns([12, 8])
    preset_names = list(PRESET_SCENARIOS.keys())

    with c_sel:
        st.markdown("**Select Scenarios to Compare (Choose 2 to 5)**")
        selected_scenarios = st.multiselect(
            "Scenarios",
            options=preset_names,
            default=["Baseline Policy", "High Fuel Price (+50%)", "Strict Emission Cap"],
            help="Select scenarios to evaluate and chart side-by-side.",
        )

    with c_custom:
        with st.expander("Custom Stress Scenario Builder", expanded=False):
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                c_fp = st.slider("Fuel Price Multiplier", 0.5, 2.5, 1.0, 0.1, help="Bunker price scaling factor.")
                c_dem = st.slider("Demand Multiplier", 0.5, 2.0, 1.0, 0.05, help="Corridor cargo demand scaling factor.")
            with c_p2:
                c_spd = st.slider("Speed Cap Delta (knots)", -4.0, 2.0, 0.0, 0.5, help="Speed limit adjustment.")
                c_ci = st.slider("Carbon Intensity Cap", 10.0, 25.0, 18.0, 1.0, help="Regulatory CII target.")
            c_sp = st.checkbox("Mandatory Port Shore Power", value=False)
            add_custom = st.button("Add Custom Scenario to Comparison", width="stretch")

    if "custom_scenarios" not in st.session_state:
        st.session_state["custom_scenarios"] = {}

    if add_custom:
        custom_name = f"Custom (P:{c_fp}x, D:{c_dem}x)"
        st.session_state["custom_scenarios"][custom_name] = {
            "description": "User-defined custom stress scenario",
            "fuel_price_multiplier": c_fp,
            "demand_multiplier": c_dem,
            "weather_multiplier": 1.0,
            "speed_cap_delta": c_spd,
            "carbon_intensity_cap": c_ci,
            "shore_power_forced": True if c_sp else None,
        }
        if custom_name not in selected_scenarios:
            selected_scenarios.append(custom_name)

    # Ensure at least 2 scenarios selected
    if len(selected_scenarios) < 2:
        st.warning("Please select at least 2 scenarios to display side-by-side comparative analysis.")
    else:
        # --- 2. Evaluate Selected Scenarios with Session Caching ---
        if "scenario_cache" not in st.session_state:
            st.session_state["scenario_cache"] = {}

        cache = st.session_state["scenario_cache"]
        to_run = [s for s in selected_scenarios if s not in cache]

        c_run, _ = st.columns([3, 7])
        recompute_clicked = c_run.button("Run scenario comparison", type="primary", width="stretch")

        if recompute_clicked or to_run:
            with st.spinner("Simulating and optimizing fleet under selected scenario constraints..."):
                for s_name in selected_scenarios:
                    if recompute_clicked or s_name not in cache:
                        override = st.session_state["custom_scenarios"].get(s_name)
                        res = evaluate_scenario(
                            scenario_name=s_name,
                            params_override=override,
                            pop_size=30,
                            generations=50,
                            random_seed=42,
                            config=cfg,
                        )
                        cache[s_name] = res

        # Build Comparison DataFrame
        rows = []
        for s_name in selected_scenarios:
            res = cache.get(s_name)
            if res:
                rows.append({
                    "Scenario": s_name,
                    "Operating Cost ($M)": round(res["total_operating_cost_usd"] / 1e6, 2),
                    "Lifecycle CO2e (kt)": round(res["total_emissions_co2e_tonnes"] / 1e3, 2),
                    "Total Fuel (kt HFO-eq)": round(res["total_fuel_tonnes_hfo_eq"] / 1e3, 2),
                    "Carbon Intensity (g/t-nm)": round(res["carbon_intensity_g_tnm"], 2),
                    "Vessels Deployed": sum(res["vessels_used_by_type"].values()),
                    "Feasible": "FEASIBLE" if res["is_feasible"] else "INFEASIBLE",
                })

        df_compare = pd.DataFrame(rows)

        # Comparative Grouped Bar Charts
        st.markdown("**Comparative Scenario Impacts Across Core Operational Metrics**")
        ch_cols = st.columns(3)
        with ch_cols[0]:
            with st.container(border=True):
                st.markdown("**Annual Operating Cost ($M USD)**")
                fig_cost = go.Figure(
                    go.Bar(
                        x=df_compare["Scenario"],
                        y=df_compare["Operating Cost ($M)"],
                        marker_color="#e63946",
                        text=[f"${v:.1f}M" for v in df_compare["Operating Cost ($M)"]],
                        textposition="auto",
                    )
                )
                apply_theme_layout(fig_cost, yaxis_title="Cost ($M USD)", height=260, show_legend=False)
                st.plotly_chart(fig_cost, width="stretch")

        with ch_cols[1]:
            with st.container(border=True):
                st.markdown("**Lifecycle Emissions (kt CO2e)**")
                fig_emiss = go.Figure(
                    go.Bar(
                        x=df_compare["Scenario"],
                        y=df_compare["Lifecycle CO2e (kt)"],
                        marker_color="#2a9d8f",
                        text=[f"{v:.1f} kt" for v in df_compare["Lifecycle CO2e (kt)"]],
                        textposition="auto",
                    )
                )
                apply_theme_layout(fig_emiss, yaxis_title="Emissions (kt CO2e)", height=260, show_legend=False)
                st.plotly_chart(fig_emiss, width="stretch")

        with ch_cols[2]:
            with st.container(border=True):
                st.markdown("**Carbon Intensity (g/t-nm)**")
                fig_ci = go.Figure(
                    go.Bar(
                        x=df_compare["Scenario"],
                        y=df_compare["Carbon Intensity (g/t-nm)"],
                        marker_color="#1d3557",
                        text=[f"{v:.1f}" for v in df_compare["Carbon Intensity (g/t-nm)"]],
                        textposition="auto",
                    )
                )
                apply_theme_layout(fig_ci, yaxis_title="Intensity (g/t-nm)", height=260, show_legend=False)
                st.plotly_chart(fig_ci, width="stretch")

        # Detailed Table
        with st.expander("Detailed Cross-Scenario Comparative Metrics Table", expanded=False):
            st.dataframe(
                df_compare,
                column_config={
                    "Operating Cost ($M)": st.column_config.NumberColumn(format="$%.2fM"),
                    "Lifecycle CO2e (kt)": st.column_config.NumberColumn(format="%.2f kt"),
                    "Total Fuel (kt HFO-eq)": st.column_config.NumberColumn(format="%.2f kt"),
                    "Carbon Intensity (g/t-nm)": st.column_config.NumberColumn(format="%.2f g/t-nm"),
                    "Vessels Deployed": st.column_config.NumberColumn(format="%d vessels"),
                },
                hide_index=True,
                width="stretch",
            )

with scen_tab2:
    st.markdown("### Carbon Tax & Bunker Price Break-Even Heatmap")
    st.caption("Precomputed 2D grid evaluating the economic tipping point where alternative green marine fuels become cost-effective.")

    be_data = get_or_load_breakeven_grid()
    if be_data is not None:
        df_grid = be_data["df_grid"]
        first_cp = be_data.get("first_green_carbon_price_nominal", 80.0)

        fig_heat = build_breakeven_heatmap(df_grid)
        st.plotly_chart(fig_heat, width="stretch")

        col_t1, col_t2 = st.columns([12, 8])
        with col_t1:
            st.info(
                f"**Break-Even Tipping Point:** Under nominal bunker fuel prices (1.00x), alternative clean fuels "
                f"enter the optimal fleet deployment at a carbon tax of **${first_cp:.0f} / t CO2e**."
            )
        with col_t2:
            st.caption("⚠️ *All values in this sensitivity grid are derived from illustrative Phase-1 parameters.*")
    else:
        st.info("Break-even grid is being precomputed by scripts/run_experiments.py...")
