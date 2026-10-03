"""
Alternative Fuels Page - Lifecycle Emissions, Energy Density & Techno-Economic Comparison.
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
from src.analysis.fuels import compare_fuels_for_voyage

st.set_page_config(page_title="Alternative Fuels | Green Fleet", page_icon="🧪", layout="wide")

st.title("🧪 Alternative Marine Fuels Evaluation")
st.markdown("Comparative techno-economic and Well-to-Wake lifecycle assessment of conventional and zero/low-carbon marine fuels.")

st.info("**SYNTHETIC NOTICE:** Fuel prices, energy densities, and emissions factors are illustrative parameters from config/params.yaml.")

cfg = load_config()

# Controls
st.subheader("1. Voyage Configuration & Production Pathways")

c1, c2 = st.columns(2)

with c1:
    vessel_sel = st.selectbox(
        "Vessel Class",
        options=list(cfg["vessel_types"].keys()),
        index=1,
        format_func=lambda x: cfg["vessel_types"][x]["name"],
    )
    v_data = cfg["vessel_types"][vessel_sel]
    
    route_sel = st.selectbox(
        "Reference Route",
        options=list(cfg["routes"].keys()),
        index=0,
        format_func=lambda x: f"{x}: {cfg['routes'][x]['name']} ({cfg['routes'][x]['distance_nm']} nm)",
    )

with c2:
    st.markdown("**Production Pathway Selectors:**")
    meth_pathway = st.selectbox("Methanol Pathway", ["green", "blue", "grey"], index=0, help="Green = e-methanol/biogenic, Blue = gas+CCS, Grey = fossil gas")
    nh3_pathway = st.selectbox("Ammonia Pathway", ["green", "blue", "grey"], index=0, help="Green = renewable H2 Haber-Bosch, Blue = Haber-Bosch+CCS, Grey = fossil")
    h2_pathway = st.selectbox("Liquid Hydrogen Pathway", ["green", "blue", "grey"], index=0, help="Green = renewable electrolysis, Blue = SMR+CCS, Grey = SMR")

pathway_choices = {
    "Methanol": meth_pathway,
    "Ammonia": nh3_pathway,
    "Hydrogen": h2_pathway,
}

df_fuels = compare_fuels_for_voyage(
    vessel_key=vessel_sel,
    route_key=route_sel,
    speed_knots=float(v_data["v_ref_knots"]),
    cargo_load_tonnes=float(v_data["l_ref_tonnes"]),
    pathway_choices=pathway_choices,
    config=cfg,
)

# 2. Comparison Table
st.markdown("---")
st.subheader("2. Single Voyage Techno-Economic Comparison")

st.dataframe(
    df_fuels[
        [
            "display_name",
            "pathway",
            "fuel_mass_tonnes",
            "energy_gj",
            "fuel_price_usd_tonne",
            "fuel_cost_usd",
            "ttw_co2e_tonnes",
            "wtt_co2e_tonnes",
            "lifecycle_co2e_tonnes",
            "cargo_loss_pct",
            "usable_teu",
            "bunkering_feasible",
        ]
    ].rename(
        columns={
            "display_name": "Fuel",
            "pathway": "Pathway",
            "fuel_mass_tonnes": "Mass (t)",
            "energy_gj": "Energy (GJ)",
            "fuel_price_usd_tonne": "Price ($/t)",
            "fuel_cost_usd": "Fuel Cost ($)",
            "ttw_co2e_tonnes": "TtW CO2e (t)",
            "wtt_co2e_tonnes": "WtT CO2e (t)",
            "lifecycle_co2e_tonnes": "Total CO2e (t)",
            "cargo_loss_pct": "Cargo Loss (%)",
            "usable_teu": "Net TEU",
            "bunkering_feasible": "Bunker Port Feasible?",
        }
    ),
    width="stretch",
)

# 3. Charts
st.markdown("---")
st.subheader("3. Lifecycle Emissions & Cost Trade-Offs")

ch1, ch2 = st.columns(2)

with ch1:
    st.markdown("##### Well-to-Wake Lifecycle GHG Emissions Breakdown")
    fig_emiss = px.bar(
        df_fuels,
        x="fuel_type",
        y=["ttw_co2e_tonnes", "wtt_co2e_tonnes", "slip_co2e_tonnes"],
        labels={"value": "CO2e Emissions (tonnes)", "fuel_type": "Fuel", "variable": "Emission Segment"},
        title="Tank-to-Wake vs Well-to-Tank vs Unburned Slip",
        barmode="stack",
        color_discrete_map={
            "ttw_co2e_tonnes": "#ef4444",
            "wtt_co2e_tonnes": "#f59e0b",
            "slip_co2e_tonnes": "#8b5cf6",
        },
    )
    fig_emiss.update_layout(template="plotly_white", height=380)
    st.plotly_chart(fig_emiss, width="stretch")

with ch2:
    st.markdown("##### Fuel Procurement Cost vs Usable Cargo Loss")
    fig_cost = px.bar(
        df_fuels,
        x="fuel_type",
        y="fuel_cost_usd",
        color="cargo_loss_pct",
        color_continuous_scale="Viridis",
        labels={"fuel_cost_usd": "Voyage Fuel Cost ($ USD)", "cargo_loss_pct": "Cargo Loss (%)"},
        title="Voyage Fuel Cost & Volumetric Tank Penalty",
    )
    fig_cost.update_layout(template="plotly_white", height=380)
    st.plotly_chart(fig_cost, width="stretch")

st.caption(
    "**Decarbonization Insight:** While green ammonia and hydrogen achieve near-zero combustion emissions at the tailpipe (TtW), their lifecycle benefit depends strictly on renewable production (electrolysis/green ammonia synthesis), and their lower volumetric density imposes up to 14% cargo slot capacity penalties."
)
