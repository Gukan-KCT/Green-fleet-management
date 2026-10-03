"""
Shore Power Page - Cold Ironing Grid vs Onboard Auxiliary Diesel Generator Analysis.
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
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.analysis.shore_power import analyze_shore_power_fleet

st.set_page_config(page_title="Shore Power | Green Fleet", page_icon="🔌", layout="wide")

st.title("🔌 Shore Power (Cold Ironing) Analysis")
st.markdown("Quantifying port-side decarbonization, air quality benefits, and energy costs of High-Voltage Shore Connections.")

st.info("**SYNTHETIC NOTICE:** Port electricity tariffs, grid emission factors, and auxiliary hoteling loads are illustrative parameters.")

cfg = load_config()


@st.cache_data(show_spinner="Evaluating fleet shore power dynamics...")
def get_cached_shore_power():
    prob = FleetOptimizationProblem(config=cfg)
    qiea = QIEA(
        n_bits=prob.n_bits,
        pop_size=20,
        generations=30,
        random_seed=42,
        initial_theta=prob.get_initial_q_angles(),
    )
    res = qiea.optimize(prob.fitness_function)
    eval_res = prob.evaluate(res["best_bits"])
    return analyze_shore_power_fleet(eval_res, config=cfg)


sp_analysis = get_cached_shore_power()
summary = sp_analysis["summary"]
df_ports = sp_analysis["port_breakdown"]
benefits = summary["net_benefit"]

# 1. Headline Decarbonization & Economic Savings
st.subheader("1. Port Network Cold-Ironing Benefits")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Annual Port Calls", f"{summary['annual_port_calls_total']:,.0f} Calls")
k2.metric("In-Port MGO Saved", f"{benefits['fuel_saved_tonnes']:,.1f} t", f"-{benefits['fuel_reduction_pct']}% Burn")
k3.metric("Port CO2e Avoided", f"{benefits['co2_avoided_tonnes']:,.1f} t", f"-{benefits['co2_reduction_pct']}% Emissions")
k4.metric("Net Economic Impact", f"${benefits['cost_savings_usd']:,.0f}", help="Cost difference between grid tariffs and bunker MGO")

# 2. Port Terminal Breakdown Table
st.markdown("---")
st.subheader("2. Port-by-Port Operational Breakdown")

st.dataframe(
    df_ports[
        [
            "port_name",
            "has_shore_power",
            "annual_port_calls",
            "aux_energy_mwh",
            "grid_ef_tonnes_mwh",
            "no_sp_mgo_tonnes",
            "no_sp_emissions_co2e",
            "with_sp_emissions_co2e",
            "co2_avoided_tonnes",
            "co2_reduction_pct",
            "cost_savings_usd",
        ]
    ].rename(
        columns={
            "port_name": "Port Terminal",
            "has_shore_power": "Shore Power Ready?",
            "annual_port_calls": "Port Calls",
            "aux_energy_mwh": "Aux Energy (MWh)",
            "grid_ef_tonnes_mwh": "Grid EF (t/MWh)",
            "no_sp_mgo_tonnes": "Aux Gen MGO (t)",
            "no_sp_emissions_co2e": "Aux Gen CO2e (t)",
            "with_sp_emissions_co2e": "Shore Power CO2e (t)",
            "co2_avoided_tonnes": "CO2e Avoided (t)",
            "co2_reduction_pct": "CO2e Reduction (%)",
            "cost_savings_usd": "Net Cost Delta ($)",
        }
    ),
    width="stretch",
)

# 3. Visual Charts
st.markdown("---")
st.subheader("3. In-Port Emissions & Cost Comparison")

c1, c2 = st.columns(2)

with c1:
    st.markdown("##### In-Port GHG Emissions: Auxiliary Generator vs Cold Ironing")
    fig_em = px.bar(
        df_ports,
        x="port_id",
        y=["no_sp_emissions_co2e", "with_sp_emissions_co2e"],
        barmode="group",
        labels={"value": "In-Port Emissions (t CO2e)", "port_id": "Port", "variable": "Policy"},
        title="Port-Side Emissions by Terminal",
        color_discrete_map={"no_sp_emissions_co2e": "#ef4444", "with_sp_emissions_co2e": "#10b981"},
    )
    fig_em.update_layout(template="plotly_white", height=380)
    st.plotly_chart(fig_em, width="stretch")

with c2:
    st.markdown("##### Annual In-Port Operating Energy Cost")
    fig_cost = px.bar(
        df_ports,
        x="port_id",
        y=["no_sp_cost_usd", "with_sp_cost_usd"],
        barmode="group",
        labels={"value": "Annual Berth Energy Cost ($ USD)", "port_id": "Port", "variable": "Policy"},
        title="In-Port Energy Expenditure",
        color_discrete_map={"no_sp_cost_usd": "#64748b", "with_sp_cost_usd": "#3b82f6"},
    )
    fig_cost.update_layout(template="plotly_white", height=380)
    st.plotly_chart(fig_cost, width="stretch")

st.caption(
    "**Operational Finding:** At ports with clean regional electric grids (e.g. Singapore, Colombo), cold-ironing eliminates diesel exhaust particulate matter and yields dramatic lifecycle emissions reductions. However, at terminals lacking cold-ironing infrastructure (e.g. Tuticorin), vessels must rely on compliant MGO auxiliary generation."
)
