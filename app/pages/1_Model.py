"""
Model Page - Mathematical Physics & Economic Formulations.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config

st.set_page_config(page_title="Mathematical Model | Green Fleet", page_icon="📐", layout="wide")

st.title("📐 Mathematical & Economic Model")
st.markdown("Mathematical formulations and physical principles governing fleet fuel consumption, emissions, costs, and constraints.")

st.info("**SYNTHETIC NOTICE:** All parameter values and mathematical formulas are illustrative models designed for prototype demonstration.")

cfg = load_config()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. Hydrodynamics & Fuel",
    "2. Alternative Fuels & Emissions",
    "3. Operating Costs & Reliability",
    "4. Shore Power & Berth",
    "5. System Configuration Tables",
])

with tab1:
    st.subheader("1. Propulsion Power & Leg Fuel Consumption")
    st.markdown(
        """
        Fuel consumption per sea leg is modeled by compounding cubic speed laws, Admiralty displacement scaling,
        stochastic weather penalties, and transit durations:
        """
    )
    st.latex(r"F_{\text{leg}} = F_{\text{daily}}(V) \times \Phi_{\text{load}}(L) \times \Psi_{\text{weather}}(S_w) \times T_{\text{leg}}(V, d)")

    st.markdown("#### (a) Cubic Speed Effect")
    st.markdown("Vessel hydrodynamic resistance scales with velocity squared; power and daily fuel burn scale with velocity cubed:")
    st.latex(r"F_{\text{daily}}(V) = F_{\text{ref}} \left(\frac{V}{V_{\text{ref}}}\right)^3")
    st.caption("Where $F_{\text{ref}}$ is daily fuel burn at reference service speed $V_{\text{ref}}$.")

    st.markdown("#### (b) Cargo Payload & Displacement Effect")
    st.markdown("Based on the classical Admiralty coefficient law relating power to immersed displacement $\nabla^{2/3}$:")
    st.latex(r"\Phi_{\text{load}}(L) = \left(\frac{\Delta_{\text{lightship}} + L}{\Delta_{\text{lightship}} + L_{\text{ref}}}\right)^{2/3}")
    st.caption("Where $\Delta_{\text{lightship}}$ is vessel empty hull mass, $L$ is cargo payload, and $L_{\text{ref}}$ is design payload.")

    st.markdown("#### (c) Hydrodynamic Weather Penalty")
    st.markdown("Accounts for wind resistance and wave drift added resistance:")
    st.latex(r"\Psi_{\text{weather}}(S_w) = 1 + k_w \cdot S_w, \quad S_w \in [0, 1]")
    st.caption(f"Configured weather coefficient $k_w = {cfg['general'].get('weather_penalty_k_w', 0.35)}$.")

    st.markdown("#### (d) Transit Duration")
    st.latex(r"T_{\text{leg}} = \frac{d}{24 \cdot V} \quad (\text{days})")

with tab2:
    st.subheader("2. Alternative Fuels & Well-to-Wake Lifecycle Emissions")
    
    st.markdown("#### (a) Energy Equivalence Conversion")
    st.markdown(
        """
        Alternative fuel mass $M_{\text{alt}}$ is computed by equating net propulsive energy delivered to the shaft,
        accounting for differences in Lower Heating Value ($LHV$) and relative thermal engine efficiency:
        """
    )
    st.latex(r"M_{\text{alt}} = M_{\text{conv}} \cdot \left(\frac{LHV_{\text{conv}}}{LHV_{\text{alt}}}\right) \cdot \frac{1}{\eta_{\text{rel}}}")
    
    st.markdown("#### (b) Well-to-Wake Lifecycle Emissions")
    st.markdown("Well-to-Wake (WtW) emissions encompass both fuel production/supply chain and onboard combustion:")
    st.latex(r"E_{\text{total}} = M_{\text{fuel}} \cdot \Big(EF_{\text{TtW}} + EF_{\text{WtT}}(\text{pathway})\Big) + M_{\text{fuel}} \cdot \xi_{\text{slip}}")
    st.markdown(
        r"""
        - $EF_{\text{TtW}}$: Tank-to-Wake emission factor (combustion tailpipe).
        - $EF_{\text{WtT}}$: Well-to-Tank emission factor based on production pathway (grey, blue, green).
        - $\xi_{\text{slip}}$: Unburned slip penalty (e.g. methane slip for LNG, $N_2O$ slip for ammonia).
        """
    )

    st.markdown("#### (c) Cargo Capacity Volumetric Penalty")
    st.markdown("Alternative fuels (ammonia, methanol, hydrogen) have lower volumetric energy densities, requiring larger bunker tanks:")
    st.latex(r"\text{Capacity}_{\text{usable}} = \text{Capacity}_{\text{nominal}} \times \left(1 - \frac{\delta_{\text{penalty}}}{100}\right)")

with tab3:
    st.subheader("3. Total Operating Cost & Schedule Reliability")
    
    st.markdown("#### (a) Annual Fleet Operating Cost Formulation")
    st.latex(r"C_{\text{total}} = C_{\text{fuel}} + C_{\text{charter}} + C_{\text{port\_fees}} + C_{\text{shore\_power}} + \tau_{\text{carbon}} \cdot E_{\text{total}}")
    carbon_tax = cfg['general']['carbon_price_usd_per_tonne']
    st.markdown(
        r"""
        - $C_{\text{fuel}}$: Direct fuel bunkering expenditure based on pathway-specific market prices.
        - $C_{\text{charter}}$: Fixed time-charter / capital amortized cost per vessel operating day.
        - $C_{\text{port\_fees}}$: Terminal mooring and harbor pilotage call fees.
        - $C_{\text{shore\_power}}$: Port electric grid utility bills during cold-ironing.
        - $\tau_{\text{carbon}}$: Regulatory carbon price ($""" + f"{carbon_tax:.0f}" + r""" / t CO2e).
        """
    )

    st.markdown("#### (b) Schedule Reliability Formulation")
    st.markdown("Operational reliability index drops non-linearly near engine maximum rating (no schedule slack for recovery) and drops with adverse seas:")
    st.latex(r"R(V, S_w) = \max\left(0, \min\left(1.0, 1.0 - 0.25 \left(\frac{V}{V_{\max}}\right)^2 - 0.20 \cdot S_w\right)\right)")

with tab4:
    st.subheader("4. Port Shore Power (Cold Ironing) Mechanics")
    st.markdown("Auxiliary electric load consumed while tied to berth:")
    st.latex(r"E_{\text{berth}} = Aux_{\text{kW}} \times \text{BerthHours} \quad (\text{kWh})")
    
    st.markdown(
        """
        - **With Shore Power (if available at port):**
          Vessel connects to shore grid. Fuel burn = 0. Emissions = $E_{\text{berth}} \times EF_{\text{grid}}$. Cost = $E_{\text{berth}} \times \text{Tariff}_{\text{grid}}$.
        - **Without Shore Power:**
          Vessel burns Marine Gas Oil (MGO) in 4-stroke auxiliary engines with specific fuel oil consumption $SFOC \approx 210 \text{ g/kWh}$.
        """
    )

with tab5:
    st.subheader("5. System Configuration Tables")
    
    st.markdown("##### Vessel Types Registry")
    v_rows = []
    for vk, v in cfg["vessel_types"].items():
        v_rows.append({
            "Vessel ID": vk,
            "Name": v["name"],
            "Capacity (TEU)": v["capacity_teu"],
            "DWT (tonnes)": v["capacity_dwt"],
            "V_min - V_max (kn)": f"{v['v_min_knots']} - {v['v_max_knots']}",
            "F_ref (t/day)": v["f_ref_tonnes_day"],
            "Charter ($/day)": f"${v['daily_charter_usd']:,.0f}",
            "Aux kW": v["aux_kw_berth"],
            "Available": v["fleet_available"],
        })
    st.dataframe(pd.DataFrame(v_rows), width="stretch")

    st.markdown("##### Marine Fuels Registry")
    f_rows = []
    for fk, f in cfg["fuels"].items():
        f_rows.append({
            "Fuel": fk,
            "Name": f["name"],
            "LHV (MJ/kg)": f["lhv_mj_kg"],
            "Engine Eff Ratio": f["engine_efficiency_ratio"],
            "TtW EF (t/t)": f["ef_tank_to_wake"],
            "Capacity Loss (%)": f"{f.get('capacity_penalty_pct', 0.0)}%",
            "Pathways": ", ".join(f.get("pathways", ["fossil"])),
        })
    st.dataframe(pd.DataFrame(f_rows), width="stretch")

    st.markdown("##### Regional Ports Registry")
    p_rows = []
    for pk, p in cfg["ports"].items():
        p_rows.append({
            "Port ID": pk,
            "Port Name": p["name"],
            "Country": p["country"],
            "Shore Power Available": "Yes" if p["has_shore_power"] else "No",
            "Grid EF (t/MWh)": p["grid_ef_tonnes_per_mwh"],
            "Electricity Tariff ($/MWh)": f"${p['electricity_price_usd_per_mwh']:.0f}",
            "Berth Hours (avg)": p["berth_hours_avg"],
            "Supported Fuels": ", ".join(p["supported_fuels"]),
        })
    st.dataframe(pd.DataFrame(p_rows), width="stretch")

    st.markdown("##### Feeder Corridors (Base Network)")
    r_rows = []
    for rk, r in cfg["routes"].items():
        r_rows.append({
            "Route ID": rk,
            "Name": r["name"],
            "Origin": r["origin"].title(),
            "Destination": r["destination"].title(),
            "Distance (nm)": r["distance_nm"],
            "Annual Demand (TEU)": f"{r['annual_demand_teu']:,}",
            "Min Sailings/Wk": r["min_sailings_per_week"],
            "Weather Severity": r["weather_severity"],
            "Speed Cap (kn)": r["speed_cap_knots"],
        })
    st.dataframe(pd.DataFrame(r_rows), width="stretch")
