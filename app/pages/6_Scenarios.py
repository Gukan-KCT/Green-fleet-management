"""
Scenarios Page - Sensitivity & Macroeconomic Stress-Testing.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config
from src.analysis.scenarios import (
    PRESET_SCENARIOS,
    run_all_preset_scenarios,
    evaluate_scenario,
)

st.set_page_config(page_title="Scenarios | Green Fleet", page_icon="🌐", layout="wide")

st.title("🌐 Sensitivity & Scenario Analysis")
st.markdown("Stress-testing fleet decarbonization and operating cost resilience under macroeconomic, operational, and regulatory shifts.")

st.info("**SYNTHETIC NOTICE:** Preset and custom scenario variations test synthetic parameters and illustrative fleet configurations.")

cfg = load_config()

tab_presets, tab_custom = st.tabs(["1. Preset Scenarios Benchmark", "2. Custom Scenario Builder"])

with tab_presets:
    st.subheader("1. Standard Stress-Testing Presets")
    st.markdown("Compares 6 representative operating environments evaluated via QIEA:")
    
    @st.cache_data(show_spinner="Evaluating all preset scenarios with QIEA...")
    def get_cached_presets():
        return run_all_preset_scenarios(pop_size=15, generations=25, random_seed=42, config=cfg)
    
    df_summary, details_map = get_cached_presets()
    
    st.dataframe(df_summary, width="stretch")
    
    # Visual comparison
    st.markdown("##### Scenario Comparison: Costs vs Lifecycle Emissions")
    fig_scen = px.scatter(
        df_summary,
        x="Total Cost ($M)",
        y="GHG Emissions (kt CO2e)",
        size="Total Fuel (t HFO-eq)",
        color="Scenario",
        text="Scenario",
        hover_data=["Carbon Intensity (g/t-nm)", "Feasible"],
        title="Macro Scenario Trade-Off Landscape",
    )
    fig_scen.update_traces(textposition="top center")
    fig_scen.update_layout(template="plotly_white", height=420)
    st.plotly_chart(fig_scen, width="stretch")

with tab_custom:
    st.subheader("2. Interactive Custom Scenario Simulation")
    st.markdown("Configure custom market, climate, or regulatory perturbations and re-run the optimization engine:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        f_mult = st.slider("Fuel Price Multiplier (1.0 = Baseline)", 0.50, 2.50, 1.25, 0.05)
        d_mult = st.slider("Cargo Demand Multiplier (1.0 = Baseline)", 0.70, 1.60, 1.10, 0.05)
        w_mult = st.slider("Weather Severity Multiplier", 0.50, 2.00, 1.20, 0.10)
    
    with col2:
        speed_delta = st.slider("Speed Ceiling Delta (knots)", -4.0, 2.0, -1.5, 0.5)
        ci_cap = st.slider("Carbon Intensity Proxy Cap (g/t-nm)", 8.0, 24.0, 15.0, 1.0)
        sp_choice = st.selectbox("Shore Power Policy", ["Automatic (Optimized)", "Mandatory On (All Ready Ports)", "Mandatory Off"])
        
        sp_forced = None
        if sp_choice == "Mandatory On (All Ready Ports)":
            sp_forced = True
        elif sp_choice == "Mandatory Off":
            sp_forced = False
    
    if st.button("🚀 Evaluate Custom Scenario", type="primary"):
        with st.spinner("Optimizing fleet schedule under custom scenario..."):
            custom_res = evaluate_scenario(
                scenario_name="Custom User Scenario",
                params_override={
                    "fuel_price_multiplier": f_mult,
                    "demand_multiplier": d_mult,
                    "weather_multiplier": w_mult,
                    "speed_cap_delta": speed_delta,
                    "carbon_intensity_cap": ci_cap,
                    "shore_power_forced": sp_forced,
                },
                pop_size=20,
                generations=30,
                random_seed=42,
                config=cfg,
            )
            st.session_state["custom_scenario_res"] = custom_res
    
    if "custom_scenario_res" in st.session_state:
        c_res = st.session_state["custom_scenario_res"]
        st.markdown("---")
        st.markdown("#### Custom Scenario Optimization Outcome")
        
        cm1, cm2, cm3, cm4, cm5 = st.columns(5)
        cm1.metric("Fuel Burn", f"{c_res['total_fuel_tonnes_hfo_eq']:,.0f} t")
        cm2.metric("Total Cost", f"${c_res['total_operating_cost_usd'] / 1e6:.2f} M")
        cm3.metric("Emissions", f"{c_res['total_emissions_co2e_tonnes'] / 1e3:.2f} kt")
        cm4.metric("Carbon Intensity", f"{c_res['carbon_intensity_g_tnm']:.2f} g/t-nm")
        cm5.metric("Compliance", "Compliant ✅" if c_res["is_feasible"] else "Violations ⚠️")
        
        st.markdown(f"**Vessels Deployed:** `{c_res['vessels_used_by_type']}`")
