"""
Shore Power - Cold Ironing & Berth Decarbonization Workspace.
Evaluates port grid connections vs onboard auxiliary engine diesel generator emissions.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Shore Power | Green Fleet",
    page_icon="🔌",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, UI_COLORS
from app.ui.css import inject_css
from app.ui.state import get_default_config, get_or_load_plan
from src.analysis.shore_power import analyze_shore_power_fleet

render_top_strip(
    title="Port Shore Power (Cold Ironing)",
    subtitle="Assess auxiliary generator fuel displacement against municipal electric grid carbon factors.",
)
inject_css()

cfg = get_default_config()
plan = get_or_load_plan()
opt_eval = plan["optimized_eval"]

# --- 1. Interactive Port Shore Power Connectivity Strip ---
ports_cfg = cfg.get("ports", {})

st.markdown("**Regional Port Cold-Ironing Terminal Grid Status**")
st.caption("Toggle cold-ironing connectivity for enabled terminals. Ports lacking infrastructure are disabled.")

port_cols = st.columns(len(ports_cfg))
port_states = {}

for i, (p_id, p_info) in enumerate(ports_cfg.items()):
    has_sp = bool(p_info.get("has_shore_power", False))
    p_name = p_info.get("name", p_id.title()).split("(")[0].strip()
    with port_cols[i]:
        with st.container(border=True):
            if has_sp:
                is_on = st.checkbox(
                    p_name,
                    value=True,
                    key=f"sp_port_{p_id}",
                    help=f"Grid EF: {p_info.get('grid_ef_tonnes_per_mwh', 0.65)} t/MWh. Tariff: ${p_info.get('electricity_price_usd_per_mwh', 120)}/MWh.",
                )
                port_states[p_id] = is_on
                st.caption("Active Grid Link")
            else:
                st.checkbox(
                    p_name,
                    value=False,
                    disabled=True,
                    key=f"sp_port_{p_id}",
                    help="Disabled: Terminal lacks high-voltage shore connection (HVSC) substation.",
                )
                port_states[p_id] = False
                st.caption("No Grid Link")

# Run Shore Power Analysis
sp_res = analyze_shore_power_fleet(opt_eval, config=cfg)
summary = sp_res["summary"]
net = summary["net_benefit"]
df_ports = sp_res["port_breakdown"]

# --- 2. KPI Cards ---
kpi_cols = st.columns(3)
with kpi_cols[0]:
    with st.container(border=True):
        st.metric(
            label="Port Fuel Avoided (t MGO)",
            value=f"{net['fuel_saved_tonnes']:,.1f} t",
            delta=f"-{net['fuel_reduction_pct']:.1f}% MGO burn",
            delta_color="normal",
            help="Displaced auxiliary generator marine gasoil while at berth.",
        )
with kpi_cols[1]:
    with st.container(border=True):
        st.metric(
            label="Port Berth CO2e Avoided",
            value=f"{net['co2_avoided_tonnes']:,.1f} t",
            delta=f"-{net['co2_reduction_pct']:.1f}% berth emissions",
            delta_color="normal",
            help="Net Well-to-Wake CO2e reduction accounting for municipal grid emission intensity.",
        )
with kpi_cols[2]:
    with st.container(border=True):
        cost_diff = net['cost_savings_usd']
        sign = "+" if cost_diff > 0 else ""
        st.metric(
            label="Net Berth Cost Delta",
            value=f"${abs(int(cost_diff)):,}",
            delta=f"{sign}${int(cost_diff):,} net delta",
            delta_color="inverse" if cost_diff > 0 else "normal",
            help="Electricity purchasing costs minus avoided MGO bunker fuel expenditure.",
        )

# --- 3. With vs Without Shore Power Comparison Charts ---
c_ch1, c_ch2 = st.columns(2)

without_sp = summary["without_shore_power"]
with_sp = summary["with_max_shore_power"]

with c_ch1:
    with st.container(border=True):
        st.markdown("**Berth Greenhouse Gas Emissions (tonnes CO2e)**")
        st.caption("100% Onboard Auxiliary Engines vs High-Voltage Cold Ironing.")
        fig_emiss = go.Figure(
            go.Bar(
                x=["Without Shore Power (MGO)", "With Shore Power (Grid)"],
                y=[without_sp["emissions_co2e_tonnes"], with_sp["emissions_co2e_tonnes"]],
                marker_color=["#2b2d42", "#2a9d8f"],
                text=[f"{v:,.0f} t" for v in [without_sp["emissions_co2e_tonnes"], with_sp["emissions_co2e_tonnes"]]],
                textposition="auto",
                hovertemplate="%{x}: <b>%{y:,.1f} tonnes CO2e</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_emiss,
            xaxis_title="Operational Mode",
            yaxis_title="Berth Emissions (tonnes CO2e)",
            height=280,
            show_legend=False,
        )
        st.plotly_chart(fig_emiss, width="stretch")

with c_ch2:
    with st.container(border=True):
        st.markdown("**Berth Operational Expenditure ($ USD)**")
        st.caption("Marine Gasoil fuel cost vs Shore Power electricity purchasing tariffs.")
        fig_cost = go.Figure(
            go.Bar(
                x=["Without Shore Power (MGO)", "With Shore Power (Grid)"],
                y=[without_sp["operating_cost_usd"], with_sp["operating_cost_usd"]],
                marker_color=["#e63946", "#457b9d"],
                text=[f"${int(v):,}" for v in [without_sp["operating_cost_usd"], with_sp["operating_cost_usd"]]],
                textposition="auto",
                hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_cost,
            xaxis_title="Operational Mode",
            yaxis_title="Berth Energy Cost ($ USD)",
            height=280,
            show_legend=False,
        )
        st.plotly_chart(fig_cost, width="stretch")

# Detailed Table
with st.expander("Port-by-Port Operational Breakdown Table", expanded=False):
    st.dataframe(
        df_ports,
        column_config={
            "port_name": st.column_config.TextColumn("Port Terminal"),
            "has_shore_power": st.column_config.CheckboxColumn("Shore Power Available"),
            "annual_port_calls": st.column_config.NumberColumn("Annual Calls", format="%.0f"),
            "aux_energy_mwh": st.column_config.NumberColumn("Aux Energy", format="%.1f MWh"),
            "co2_avoided_tonnes": st.column_config.NumberColumn("CO2e Avoided", format="%.1f t"),
            "cost_savings_usd": st.column_config.NumberColumn("Net Cost Delta", format="$%d"),
        },
        hide_index=True,
        width="stretch",
    )

# --- 4. Interactive Single Port / Vessel OPS Arrival Calculator ---
st.markdown("---")
st.markdown("### 🔌 Interactive Single-Port Berth & OPS Calculator")
st.caption("Model vessel arrival at port → berthing duration → auxiliary hoteling energy demand → shore power availability → electricity consumption → avoided fuel & emissions.")

from src.analysis.shore_power import calculate_ops_tradeoff

c_in1, c_in2, c_in3, c_in4 = st.columns(4)
with c_in1:
    calc_port_id = st.selectbox(
        "Port Terminal",
        options=list(ports_cfg.keys()),
        format_func=lambda x: f"{ports_cfg[x]['name']} ({'OPS Ready' if ports_cfg[x].get('has_shore_power') else 'No OPS'})",
        index=0,
    )
with c_in2:
    calc_vessel_id = st.selectbox(
        "Vessel Class",
        options=list(cfg.get("vessel_types", {}).keys()),
        format_func=lambda x: cfg["vessel_types"][x].get("name", x),
        index=1,
    )
with c_in3:
    default_b_hours = float(ports_cfg[calc_port_id].get("berth_hours_avg", 24.0))
    calc_berth_hours = st.number_input("Berthing Duration (hours)", min_value=1.0, max_value=168.0, value=default_b_hours, step=1.0)
with c_in4:
    port_default_sp = bool(ports_cfg[calc_port_id].get("has_shore_power", False))
    calc_sp_avail = st.radio(
        "Shore Power Available?",
        options=[True, False],
        index=0 if port_default_sp else 1,
        format_func=lambda x: "Yes (Available)" if x else "No (Unavailable)",
        horizontal=True,
    )

c_in5, c_in6, c_in7 = st.columns(3)
with c_in5:
    default_aux = float(cfg["vessel_types"][calc_vessel_id].get("aux_kw_berth", 650.0))
    calc_aux_kw = st.number_input("Auxiliary Power Demand (kW)", min_value=50.0, max_value=5000.0, value=default_aux, step=50.0)
with c_in6:
    default_tariff = float(ports_cfg[calc_port_id].get("electricity_price_usd_per_mwh", 120.0))
    calc_tariff = st.number_input("Electricity Price ($/MWh)", min_value=20.0, max_value=500.0, value=default_tariff, step=5.0)
with c_in7:
    calc_eff = st.slider("Shore Power Connection Efficiency (η)", min_value=0.80, max_value=1.0, value=0.95, step=0.01, format="%.2f")

# Run Single Port Calculation
tradeoff = calculate_ops_tradeoff(
    port_id=calc_port_id,
    vessel_type=calc_vessel_id,
    berth_hours=calc_berth_hours,
    shore_power_available=calc_sp_avail,
    electricity_price_usd_per_mwh=calc_tariff,
    aux_power_demand_kw=calc_aux_kw,
    connection_efficiency=calc_eff,
    config=cfg,
)

if not tradeoff["ops_feasible"]:
    st.warning(f"⚠️ **OPS Connection Rejected**: {tradeoff.get('rejection_reason')}. Auxiliary diesel generator burning MGO will operate for the entire duration.")
else:
    st.success(f"✅ **OPS Active**: Connected to port electrical grid. Auxiliary diesel generator is shut down, avoiding **{tradeoff['tradeoff']['fuel_saved_tonnes']:.3f} t MGO** and cutting berth emissions by **{tradeoff['tradeoff']['percentage_reduction']:.1f}%**.")

# Display side-by-side metric comparison
col_wout, col_with, col_delta = st.columns(3)
with col_wout:
    with st.container(border=True):
        st.markdown("**WITHOUT OPS (Aux Generator)**")
        st.write(f"• Fuel Consumption: **{tradeoff['without_ops']['fuel_consumption_tonnes']:.3f} t MGO**")
        st.write(f"• Fuel Cost: **${tradeoff['without_ops']['fuel_cost_usd']:,.2f}**")
        st.write(f"• CO2e Emissions: **{tradeoff['without_ops']['co2e_tonnes']:.3f} t CO2e**")

with col_with:
    with st.container(border=True):
        st.markdown("**WITH OPS (Grid Connection)**")
        if tradeoff["ops_feasible"]:
            st.write(f"• Electricity Consumption: **{tradeoff['with_ops']['electricity_consumption_mwh']:.3f} MWh** ({tradeoff['with_ops']['electricity_consumption_kwh']:,.1f} kWh)")
            st.write(f"• Electricity Cost: **${tradeoff['with_ops']['electricity_cost_usd']:,.2f}**")
            st.write(f"• CO2e Emissions: **{tradeoff['with_ops']['co2e_tonnes']:.3f} t CO2e**")
        else:
            st.write("• Electricity Consumption: **0.00 MWh (Infeasible)**")
            st.write("• Electricity Cost: **$0.00**")
            st.write("• Fallback to Onboard Generator")

with col_delta:
    with st.container(border=True):
        st.markdown("**NET BENEFIT / DELTA**")
        st.write(f"• Fuel Saved: **{tradeoff['tradeoff']['fuel_saved_tonnes']:.3f} t MGO**")
        c_diff = tradeoff['tradeoff']['cost_difference_usd']
        st.write(f"• Cost Difference: **{'+' if c_diff >= 0 else '-'}${abs(c_diff):,.2f}**")
        st.write(f"• CO2e Avoided: **{tradeoff['tradeoff']['co2e_avoided_tonnes']:.3f} t CO2e**")
        st.write(f"• Percentage Reduction: **{tradeoff['tradeoff']['percentage_reduction']:.1f}%**")

