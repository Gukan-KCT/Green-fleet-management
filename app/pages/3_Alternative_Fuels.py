"""
Alternative Marine Fuels - Interactive Decision-Support & Fleet Optimization Engine.
Evaluates volumetric energy density, bunkering procurement costs, lifecycle emissions,
cargo capacity displacement, and connects directly to the multi-objective fleet optimizer.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Alternative Fuels | Green Fleet",
    page_icon="🌱",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, get_fuel_color
from app.ui.css import inject_css
from app.ui.state import get_default_config
from src.analysis.fuels import (
    compare_fuels_for_voyage,
    FUEL_STRUCTURED_PARAMETERS,
    VESSEL_FUEL_COMPATIBILITY,
    build_candidate_options,
)
from src.optimization.planner import optimize_fleet_plan
from src.optimization.problem import FleetOptimizationProblem
from src.analysis.decision_support import compute_carbon_intensity_rating

render_top_strip(
    title="Alternative Marine Fuels",
    subtitle="Techno-economic parameter modeling, lifecycle assessment, and fleet optimization engine.",
)

inject_css()
cfg = get_default_config()

vessel_types = list(cfg["vessel_types"].keys())
vessel_names = {k: cfg["vessel_types"][k]["name"] for k in vessel_types}

route_keys = list(cfg["routes"].keys())
route_names = {k: f"{k}: {cfg['routes'][k]['name']} ({cfg['routes'][k]['distance_nm']} nm)" for k in route_keys}

# Top Navigation / Sub-view Selection
fuel_tab1, fuel_tab2, fuel_tab3 = st.tabs([
    "📊 Single-Voyage Fuel Comparison",
    "🚀 Fleet Optimizer Integration ('Use in Optimization')",
    "📋 Parameter Models & Data Assumptions Audit",
])


# ==============================================================================
# TAB 1: SINGLE-VOYAGE FUEL COMPARISON & TECHNO-ECONOMIC MATRIX
# ==============================================================================
with fuel_tab1:
    st.markdown("### Single-Voyage Techno-Economic Assessment")
    st.caption("Compare fuel consumption, bunkering costs, lifecycle emissions, and container slot loss for a candidate voyage leg.")

    c_v, c_r, c_p = st.columns([1, 1, 1])
    with c_v:
        vessel_sel = st.selectbox(
            "Vessel Class",
            options=vessel_types,
            index=1,
            format_func=lambda x: vessel_names[x],
            help="Target vessel archetype for bunkering evaluation.",
            key="vessel_sel_tab1",
        )
    with c_r:
        route_sel = st.selectbox(
            "Corridor",
            options=route_keys,
            index=0,
            format_func=lambda x: route_names[x],
            help="Shipping lane distance, sea state, and terminal bunkering feasibility.",
            key="route_sel_tab1",
        )
    with c_p:
        pathway_sel = st.selectbox(
            "Production Pathway (for E-Fuels)",
            options=["green", "blue", "grey"],
            index=0,
            format_func=lambda x: {
                "green": "Green (Renewable Electrolysis / Bio-Feedstocks)",
                "blue": "Blue (Fossil with Carbon Capture & Storage)",
                "grey": "Grey (Unabated Fossil Reforming)",
            }[x],
            help="Upstream feedstock production pathway.",
            key="pathway_sel_tab1",
        )

    pathways = {
        "HFO": "fossil",
        "MGO": "fossil",
        "LNG": "fossil",
        "Methanol": pathway_sel,
        "Ammonia": pathway_sel,
        "Hydrogen": pathway_sel,
    }

    # Compute comparison DataFrame
    fuels_df = compare_fuels_for_voyage(
        vessel_key=vessel_sel,
        route_key=route_sel,
        pathway_choices=pathways,
        config=cfg,
    )

    # 1. KPI Cards Grid
    st.markdown("#### Candidate Fuel Metrics on Selected Corridor")
    f_cols = st.columns(len(fuels_df))
    for i, (_, row) in enumerate(fuels_df.iterrows()):
        f_name = str(row["fuel_type"])
        color = get_fuel_color(f_name)
        with f_cols[i]:
            st.markdown(
                f"""<div style="border-top:3px solid {color}; background:#fff;
                border:1px solid #e2e8f0; border-radius:10px; padding:0.85rem 0.9rem;
                box-shadow:0 1px 4px rgba(15,76,129,.08); min-height:220px;">
                <div style="color:{color};font-weight:700;font-size:13px;margin-bottom:6px;">● {f_name}</div>
                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Bunker Mass</div>
                <div style="font-size:18px;font-weight:700;color:#1e293b;">{row['fuel_mass_tonnes']:,.1f} t</div>
                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:4px;">Voyage Cost</div>
                <div style="font-size:15px;font-weight:600;color:#1e293b;">${int(row['fuel_cost_usd']):,}</div>
                <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:4px;">Lifecycle CO2e</div>
                <div style="font-size:15px;font-weight:600;color:#1e293b;">{int(row['lifecycle_co2e_tonnes']):,} t</div>
                <div style="font-size:11px;color:#64748b;margin-top:6px;">Slot penalty: <b>{row['cargo_loss_pct']:.1f}%</b></div>
                <div style="margin-top:4px;"><span style="font-size:10px; padding:2px 6px; border-radius:4px; font-weight:600; background:{'#dcfce7' if row['is_compatible'] else '#fee2e2'}; color:{'#15803d' if row['is_compatible'] else '#b91c1c'};">{'Compatible' if row['is_compatible'] else 'Incompatible'}</span></div>
                </div>""",
                unsafe_allow_html=True,
            )

    # 2. Required Standard Comparison Table
    st.markdown("#### Fuel Techno-Economic & Operational Comparison Matrix")
    req_cols = ["Fuel", "Fuel Cost", "Fuel Consumption", "Lifecycle CO2e", "Availability", "Compatibility"]
    display_table = fuels_df[req_cols].copy()
    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True,
    )

    # 3. Visualizations (2x2 Grid)
    c_ch1, c_ch2 = st.columns(2)
    with c_ch1:
        with st.container(border=True):
            st.markdown("**Required Fuel Mass (tonnes)**")
            st.caption("Mass needed to deliver equivalent propulsion energy (LHV Equivalence).")
            fig_mass = go.Figure(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["fuel_mass_tonnes"],
                    marker_color=[get_fuel_color(f) for f in fuels_df["fuel_type"]],
                    text=[f"{v:,.1f} t" for v in fuels_df["fuel_mass_tonnes"]],
                    textposition="auto",
                    hovertemplate="%{x}: <b>%{y:,.1f} tonnes</b><extra></extra>",
                )
            )
            apply_theme_layout(
                fig_mass,
                xaxis_title="Marine Fuel Candidate",
                yaxis_title="Required Mass (tonnes)",
                height=280,
                show_legend=False,
            )
            st.plotly_chart(fig_mass, use_container_width=True)

    with c_ch2:
        with st.container(border=True):
            st.markdown("**Bunker Fuel Procurement Cost ($ USD)**")
            st.caption("Fuel purchasing expenditure based on market/pathway price assumption.")
            fig_cost = go.Figure(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["fuel_cost_usd"],
                    marker_color=[get_fuel_color(f) for f in fuels_df["fuel_type"]],
                    text=[f"${int(v):,}" for v in fuels_df["fuel_cost_usd"]],
                    textposition="auto",
                    hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>",
                )
            )
            apply_theme_layout(
                fig_cost,
                xaxis_title="Marine Fuel Candidate",
                yaxis_title="Bunker Procurement ($ USD)",
                height=280,
                show_legend=False,
            )
            st.plotly_chart(fig_cost, use_container_width=True)

    c_ch3, c_ch4 = st.columns(2)
    with c_ch3:
        with st.container(border=True):
            st.markdown("**Well-to-Wake Lifecycle Emissions (tonnes CO2e)**")
            st.caption("Tank-to-Wake (combustion) vs Well-to-Tank (upstream production) vs Slip.")
            fig_emiss = go.Figure()
            fig_emiss.add_trace(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["ttw_co2e_tonnes"],
                    name="Tank-to-Wake (Combustion)",
                    marker_color="#1e293b",
                )
            )
            fig_emiss.add_trace(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["wtt_co2e_tonnes"],
                    name="Well-to-Tank (Upstream)",
                    marker_color="#0d9488",
                )
            )
            fig_emiss.add_trace(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["slip_co2e_tonnes"],
                    name="Fugitive Slip Penalty",
                    marker_color="#d97706",
                )
            )
            fig_emiss.update_layout(barmode="stack")
            apply_theme_layout(
                fig_emiss,
                xaxis_title="Marine Fuel Candidate",
                yaxis_title="Lifecycle Emissions (tonnes CO2e)",
                height=280,
                show_legend=True,
            )
            st.plotly_chart(fig_emiss, use_container_width=True)

    with c_ch4:
        with st.container(border=True):
            st.markdown("**Cargo Slot Loss / Volumetric Penalty (%)**")
            st.caption("Container slot loss from cryogenic insulation and fuel tank volume.")
            fig_pen = go.Figure(
                go.Bar(
                    x=fuels_df["fuel_type"],
                    y=fuels_df["cargo_loss_pct"],
                    marker_color="#e11d48",
                    text=[f"{v:.1f}%" for v in fuels_df["cargo_loss_pct"]],
                    textposition="auto",
                    hovertemplate="%{x}: <b>%{y:.1f}% capacity loss</b><extra></extra>",
                )
            )
            apply_theme_layout(
                fig_pen,
                xaxis_title="Marine Fuel Candidate",
                yaxis_title="Usable Capacity Penalty (%)",
                height=280,
                show_legend=False,
            )
            st.plotly_chart(fig_pen, use_container_width=True)


# ==============================================================================
# TAB 2: FLEET OPTIMIZER INTEGRATION ("USE IN OPTIMIZATION")
# ==============================================================================
with fuel_tab2:
    st.markdown("### Fuel Selection & Multi-Objective Fleet Optimizer")
    st.markdown(
        """Connect fuel choices directly into the quantum-inspired optimization engine.
        Selecting allowed fuels dynamically adjusts decision variables, vessel compatibility,
        energy conversions, bunkering constraints, and lifecycle emissions."""
    )

    # 1. Strategy Selector
    st.markdown("#### 1. Define Candidate Fuel Policy")
    col_strat1, col_strat2 = st.columns([1, 2])

    with col_strat1:
        strategy_preset = st.radio(
            "Fuel Strategy Preset",
            options=[
                "Conventional Only (HFO/MGO)",
                "LNG Transition",
                "Green Methanol Fleet",
                "Zero-Carbon Ammonia",
                "Multi-Fuel Clean Portfolio (Methanol + LNG + HFO)",
                "Full Decarbonization Portfolio (All Fuels)",
                "Custom Selection",
            ],
            index=4,
            help="Choose a preconfigured fuel transition policy or customize manually.",
        )

    # Determine default selected fuels from preset
    if strategy_preset == "Conventional Only (HFO/MGO)":
        default_fuels = ["HFO", "MGO"]
    elif strategy_preset == "LNG Transition":
        default_fuels = ["LNG"]
    elif strategy_preset == "Green Methanol Fleet":
        default_fuels = ["Methanol"]
    elif strategy_preset == "Zero-Carbon Ammonia":
        default_fuels = ["Ammonia"]
    elif strategy_preset == "Multi-Fuel Clean Portfolio (Methanol + LNG + HFO)":
        default_fuels = ["HFO", "LNG", "Methanol"]
    elif strategy_preset == "Full Decarbonization Portfolio (All Fuels)":
        default_fuels = ["HFO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
    else:
        default_fuels = ["HFO", "Methanol"]

    with col_strat2:
        all_fuels = ["HFO", "MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
        selected_fuels = st.multiselect(
            "Permitted Marine Fuels for Optimizer Decision Space",
            options=all_fuels,
            default=default_fuels,
            help="The optimizer will evaluate vessel-fuel assignments strictly from this allowed set.",
        )

        if not selected_fuels:
            st.warning("⚠️ At least one fuel must be selected. Defaulting to HFO.")
            selected_fuels = ["HFO"]

        # Production pathway overrides
        st.markdown("**Production Pathway per Fuel:**")
        pw_cols = st.columns(len(selected_fuels))
        opt_pathways = {}
        for idx, f in enumerate(selected_fuels):
            f_meta = FUEL_STRUCTURED_PARAMETERS.get(f, {})
            available_pws = list(f_meta.get("price_usd_per_tonne", {"default": 0}).keys())
            if "default" in available_pws and len(available_pws) == 1:
                available_pws = ["fossil"]
            with pw_cols[idx]:
                pw_choice = st.selectbox(
                    f"{f} Pathway",
                    options=available_pws,
                    index=0 if "green" not in available_pws else available_pws.index("green"),
                    key=f"opt_pw_{f}",
                )
                opt_pathways[f] = pw_choice

    # Display dynamically generated candidate options
    cand_preview = build_candidate_options(allowed_fuels=selected_fuels, config=cfg, pathway_map=opt_pathways)
    with st.expander(f"🔍 Inspect Optimizer Decision Space ({len(cand_preview)} Compatible Vessel-Fuel Options)", expanded=False):
        df_cand = pd.DataFrame(cand_preview)
        df_cand["Vessel Name"] = df_cand["vessel"].map(lambda v: cfg["vessel_types"][v]["name"])
        df_cand["Usable Capacity (TEU)"] = df_cand.apply(
            lambda r: int(round(cfg["vessel_types"][r["vessel"]]["capacity_teu"] * (1.0 - cfg["fuels"][r["fuel"]].get("capacity_penalty_pct", 0.0) / 100.0))),
            axis=1,
        )
        st.dataframe(
            df_cand[["Vessel Name", "vessel", "fuel", "pathway", "Usable Capacity (TEU)"]],
            use_container_width=True,
            hide_index=True,
        )

    # 2. Optimization Configuration
    st.markdown("#### 2. Fleet Optimization Objectives & Constraints")
    c_w1, c_w2, c_w3, c_sp, c_sh = st.columns(5)
    with c_w1:
        w_fuel = st.slider("Fuel Weight", 0, 100, 20, 5) / 100.0
    with c_w2:
        w_cost = st.slider("Cost Weight", 0, 100, 40, 5) / 100.0
    with c_w3:
        w_emiss = st.slider("Emissions Weight", 0, 100, 40, 5) / 100.0
    with c_sp:
        speed_cap = st.number_input("Speed Cap (knots)", min_value=12.0, max_value=22.0, value=18.0, step=0.5)
    with c_sh:
        shore_pwr = st.checkbox("Port Shore Power", value=True)

    # Normalization of weights
    tot_w = w_fuel + w_cost + w_emiss
    if tot_w > 0:
        w_fuel, w_cost, w_emiss = w_fuel / tot_w, w_cost / tot_w, w_emiss / tot_w
    else:
        w_fuel, w_cost, w_emiss = 0.2, 0.4, 0.4

    # 3. Action Button: USE IN OPTIMIZATION
    st.markdown("---")
    btn_col1, btn_col2 = st.columns([1, 2])
    with btn_col1:
        run_fuel_opt = st.button("🚀 Run Fleet Optimization with Selected Fuel(s)", type="primary", use_container_width=True)

    # Session state cache for results
    if run_fuel_opt or "last_fuel_opt_result" in st.session_state:
        if run_fuel_opt:
            with st.spinner(f"Optimizing fleet deployment across regional shipping corridors with {', '.join(selected_fuels)}..."):
                opt_res = optimize_fleet_plan(
                    allowed_fuels=selected_fuels,
                    pathway_map=opt_pathways,
                    weights={"fuel": w_fuel, "cost": w_cost, "emissions": w_emiss},
                    speed_cap=speed_cap,
                    shore_power=shore_pwr,
                    num_qiea_starts=3,
                    evals_per_start=1500,
                    seeds=[42, 43, 44],
                    config=cfg,
                )
                st.session_state["last_fuel_opt_result"] = opt_res
                st.session_state["last_fuel_opt_fuels"] = selected_fuels

        res = st.session_state.get("last_fuel_opt_result")
        if res:
            plan = res["selected_plan"]
            naive = res["naive_eval"]
            best_conv = res["best_conv_eval"]

            st.success(f"✅ Optimization complete! Status: **{res['winner_status']}** (Evaluated across {len(st.session_state.get('last_fuel_opt_fuels', selected_fuels))} permitted fuels)")

            # KPI Grid
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                opt_fuel_hfo = plan.get("total_fuel_tonnes_hfo_eq", plan.get("fuel_consumption_tonnes", 0.0))
                conv_fuel_hfo = best_conv.get("total_fuel_tonnes_hfo_eq", opt_fuel_hfo)
                diff_f = ((opt_fuel_hfo - conv_fuel_hfo) / max(1.0, conv_fuel_hfo)) * 100.0
                st.metric(
                    "Total Fuel Burn",
                    f"{opt_fuel_hfo:,.0f} t HFO-eq",
                    f"{diff_f:+.1f}% vs Conv",
                    delta_color="inverse",
                )
                st.caption(f"Energy: {plan.get('total_fuel_gj', 0):,.0f} GJ")

            with k2:
                opt_cost = plan.get("total_operating_cost_usd", plan.get("total_cost_usd", 0.0))
                conv_cost = best_conv.get("total_operating_cost_usd", opt_cost)
                diff_c = ((opt_cost - conv_cost) / max(1.0, conv_cost)) * 100.0
                st.metric(
                    "Annual Operating Cost",
                    f"${opt_cost:,.0f}",
                    f"{diff_c:+.1f}% vs Conv",
                    delta_color="inverse",
                )
                st.caption("Bunker + Charter + Port + Carbon Tax")

            with k3:
                opt_emiss = plan.get("total_emissions_co2e_tonnes", plan.get("lifecycle_co2e_tonnes", 0.0))
                conv_emiss = best_conv.get("total_emissions_co2e_tonnes", opt_emiss)
                diff_e = ((opt_emiss - conv_emiss) / max(1.0, conv_emiss)) * 100.0
                st.metric(
                    "Lifecycle GHG (WtW)",
                    f"{opt_emiss:,.0f} t CO2e",
                    f"{diff_e:+.1f}% vs Conv",
                    delta_color="inverse",
                )
                st.caption("Tank-to-Wake + Well-to-Tank + Slip")

            with k4:
                opt_ci = plan.get("carbon_intensity_g_tnm", 0.0)
                ci_rating = compute_carbon_intensity_rating(opt_ci)
                st.metric(
                    "Carbon Intensity",
                    f"{opt_ci:.1f} g/t-nm",
                    f"Rating: Grade {ci_rating['grade']}",
                    delta_color="off",
                )
                st.caption(ci_rating["description"])

            with k5:
                cargo_deliv = plan.get("total_cargo_delivered_teu", 540000)
                st.metric(
                    "Cargo Delivered",
                    f"{int(cargo_deliv):,} TEU",
                    "Demand 100% Satisfied" if plan.get("is_feasible", True) else "Demand Penalty",
                    delta_color="normal",
                )
                st.caption(f"Feasibility: {'PASS' if plan.get('is_feasible', True) else 'INVIOLABLE'}")

            # Route Corridor Deployment Table
            st.markdown("#### Fleet Deployment & Fuel Assignment by Corridor")
            prob: FleetOptimizationProblem = res["problem"]
            allocs = plan.get("allocations")

            routes_data = []
            if allocs is not None:
                for r_idx, r_key in enumerate(prob.route_keys):
                    r_cfg = prob.routes[r_key]
                    r_det = plan.get("route_details", {}).get(r_key, {})

                    opt_names = []
                    dominant_fuels = []
                    total_v = 0
                    for o_idx, opt in enumerate(prob.options):
                        n_v = int(allocs[o_idx, r_idx])
                        if n_v > 0:
                            opt_names.append(f"{n_v}x {opt['vessel']} ({opt['fuel']} - {opt.get('pathway', 'default')})")
                            dominant_fuels.append(opt["fuel"])
                            total_v += n_v

                    routes_data.append({
                        "Corridor": f"{r_key}: {r_cfg['name']}",
                        "Origin → Destination": f"{r_cfg['origin']} → {r_cfg['destination']}",
                        "Vessels Deployed": total_v,
                        "Assigned Options": ", ".join(opt_names) if opt_names else "None (Unserved)",
                        "Dominant Fuel": ", ".join(list(set(dominant_fuels))) if dominant_fuels else "None",
                        "Cruising Speed": f"{r_det.get('speed_knots', 14.0):.1f} kn",
                        "Sailings/Week": f"{r_det.get('sailings_per_week', 0.0):.2f}",
                        "Reliability (%)": f"{r_det.get('reliability', 0.0) * 100:.1f}%",
                        "Demand (TEU)": int(r_cfg["annual_demand_teu"]),
                        "Capacity (TEU)": int(round(r_det.get("annual_capacity_teu", 0))),
                    })

            st.dataframe(pd.DataFrame(routes_data), use_container_width=True, hide_index=True)


# ==============================================================================
# TAB 3: PARAMETER MODELS & DATA ASSUMPTIONS AUDIT
# ==============================================================================
with fuel_tab3:
    st.markdown("### Transparent Fuel Parameter Specifications & Assumptions")
    st.markdown(
        """All chemical, thermodynamic, and emissions parameters are grounded in peer-reviewed
        maritime studies and regulatory standards. Every assumption is explicitly classified below."""
    )

    for fuel_k, f_data in FUEL_STRUCTURED_PARAMETERS.items():
        with st.expander(f"🔹 {f_data['fuel_name']} — Specifications & Provenance", expanded=(fuel_k == "Methanol")):
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.markdown(f"**Category:** `{f_data['fuel_category']}`")
                st.markdown(f"**Energy Content (LHV):** `{f_data['energy_density_label']}`")
                st.markdown(f"**Engine Thermal Efficiency Ratio:** `{f_data['engine_efficiency_ratio']:.2f}x` vs 2-stroke diesel")
                st.markdown(f"**Cargo Volumetric Slot Loss:** `{f_data['tank_storage_factor']['capacity_penalty_pct']:.1f}%`")
                st.markdown(f"**Storage Conditions:** {f_data['tank_storage_factor']['storage_type']}")
                st.markdown(f"**Port Availability Status:** {f_data['availability_assumption']}")

            with col_b:
                st.markdown("**Lifecycle GHG Factors (t CO2e / t fuel):**")
                emiss_info = f_data["lifecycle_emissions"]
                st.markdown(f"- Tank-to-Wake (Combustion): `{emiss_info['ef_tank_to_wake']:.3f}` t CO2e/t")
                st.markdown(f"- Well-to-Tank (Upstream): `{emiss_info['ef_well_to_tank']}`")
                st.markdown(f"- Fugitive Slip Factor: `{emiss_info['slip_factor_co2e_per_tonne']:.3f}` t CO2e/t")
                st.markdown(f"- Total Well-to-Wake: `{emiss_info['total_wtw_co2e_per_tonne']}`")
                st.markdown(f"**Vessel Engine Compatibility:** `{', '.join(f_data['vessel_compatibility'])}`")

            st.markdown("**Operational & Safety Constraints:**")
            for c in f_data["operational_constraints"]:
                st.markdown(f"- {c}")

            st.markdown("**Data Source & Assumption Classification:**")
            for item_k, item_src in f_data["assumptions"].items():
                is_real = "Real / Publicly Sourced" in item_src
                is_proj = "Project Assumption" in item_src
                badge_bg = "#dcfce7" if is_real else ("#fef3c7" if is_proj else "#f1f5f9")
                badge_color = "#15803d" if is_real else ("#b45309" if is_proj else "#475569")
                st.markdown(
                    f"""<div style="display:flex; justify-content:space-between; align-items:center;
                    background:{badge_bg}; color:{badge_color}; padding:6px 12px; border-radius:6px; margin-bottom:4px; font-size:12px;">
                    <span><b>{item_k.replace('_', ' ').title()}:</b> {item_src}</span>
                    <span style="font-weight:700;">{'[REAL]' if is_real else ('[PROJECT]' if is_proj else '[SYNTHETIC]')}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
