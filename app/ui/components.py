"""
Reusable UI component helpers for Green Fleet Decision-Support Dashboard.
Implements compact header strips, signed KPI metric cards, constraint badges,
Plan Insights Cards, Carbon Intensity Gauges, and Demo Mode components.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import streamlit as st
import pandas as pd

from src.analysis.decision_support import (
    generate_plan_insights,
    compute_carbon_intensity_rating,
)


def render_top_strip(
    title: str = "Fleet Planner",
    subtitle: str = "Multi-objective maritime deployment & decarbonization workspace",
    show_presets: bool = True,
    on_preset_selected: Optional[callable] = None,
):
    """
    Renders a unified top header strip with title, slim synthetic disclosure chip,
    and optional quick preset buttons.
    """
    col_t, col_disc = st.columns([3, 2])
    with col_t:
        st.markdown(f"### {title}")
        if subtitle:
            st.caption(subtitle)
    with col_disc:
        st.markdown(
            """
            <div style="
                display:flex; gap:6px; align-items:center; flex-wrap:wrap;
                margin-top:8px; justify-content:flex-end;
            ">
              <span style="
                background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.35);
                color:#92400e; font-size:10.5px; font-weight:600; padding:2px 8px;
                border-radius:20px; letter-spacing:.04em; text-transform:uppercase;
              ">&#9670; Synthetic Data</span>
              <span style="
                background:rgba(15,76,129,.08); border:1px solid rgba(15,76,129,.2);
                color:#0f4c81; font-size:10.5px; font-weight:600; padding:2px 8px;
                border-radius:20px; letter-spacing:.04em; text-transform:uppercase;
              ">&#9632; Classical CPU</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def compute_signed_delta(opt_val: float, base_val: float) -> str:
    """
    Computes percentage change with explicit sign (+ or -).
    Never uses words like 'savings' or 'improvement'.
    """
    if base_val <= 0:
        return "N/A"
    diff_pct = ((opt_val - base_val) / base_val) * 100.0
    sign = "+" if diff_pct > 0 else ""
    return f"{sign}{diff_pct:.1f}%"


def render_kpi_row(
    opt_eval: Dict[str, Any],
    base_eval: Dict[str, Any],
    comparator_name: str = "Naive Baseline",
):
    """
    Renders 5 standard KPI metric cards in a container with inverse delta coloring
    (decreases are green, increases are red) and strict sign formatting.
    """
    cols = st.columns(5)

    # 1. Total Fuel
    opt_fuel = opt_eval.get("fuel_consumption_tonnes", opt_eval.get("total_fuel_tonnes_hfo_eq", 0.0))
    base_fuel = base_eval.get("fuel_consumption_tonnes", base_eval.get("total_fuel_tonnes_hfo_eq", 0.0))
    delta_fuel = compute_signed_delta(opt_fuel, base_fuel)
    with cols[0]:
        with st.container(border=True):
            st.metric(
                label="Total Fuel (t)",
                value=f"{int(round(opt_fuel)):,}",
                delta=f"{delta_fuel} vs {comparator_name}",
                delta_color="inverse",
                help=f"Baseline: {int(round(base_fuel)):,} t. Fuel burn across all sailing legs.",
            )

    # 2. Operating Cost
    opt_cost = opt_eval.get("total_cost_usd", opt_eval.get("total_operating_cost_usd", 0.0))
    base_cost = base_eval.get("total_cost_usd", base_eval.get("total_operating_cost_usd", 0.0))
    delta_cost = compute_signed_delta(opt_cost, base_cost)
    with cols[1]:
        with st.container(border=True):
            st.metric(
                label="Operating Cost ($)",
                value=f"${int(round(opt_cost)):,}",
                delta=f"{delta_cost} vs {comparator_name}",
                delta_color="inverse",
                help=f"Baseline: ${int(round(base_cost)):,}. Includes bunker, charter, port fees, carbon tax, shore power.",
            )

    # 3. Lifecycle Emissions
    opt_emiss = opt_eval.get("lifecycle_co2e_tonnes", opt_eval.get("total_emissions_co2e_tonnes", 0.0))
    base_emiss = base_eval.get("lifecycle_co2e_tonnes", base_eval.get("total_emissions_co2e_tonnes", 0.0))
    delta_emiss = compute_signed_delta(opt_emiss, base_emiss)
    with cols[2]:
        with st.container(border=True):
            st.metric(
                label="Lifecycle CO2e (t)",
                value=f"{int(round(opt_emiss)):,}",
                delta=f"{delta_emiss} vs {comparator_name}",
                delta_color="inverse",
                help=f"Baseline: {int(round(base_emiss)):,} t. Well-to-Wake greenhouse gas emissions.",
            )

    # 4. Carbon Intensity
    opt_ci = opt_eval.get("carbon_intensity_g_tnm", 0.0)
    base_ci = base_eval.get("carbon_intensity_g_tnm", 0.0)
    delta_ci = compute_signed_delta(opt_ci, base_ci)
    with cols[3]:
        with st.container(border=True):
            st.metric(
                label="Carbon Intensity (g/t-nm)",
                value=f"{opt_ci:.1f}",
                delta=f"{delta_ci} vs {comparator_name}",
                delta_color="inverse",
                help=f"Baseline: {base_ci:.1f} g/t-nm. Lifecycle CO2e per tonne-nautical-mile of transport work.",
            )

    # 5. Feasibility Status
    is_feas = opt_eval.get("is_feasible", True)
    with cols[4]:
        with st.container(border=True):
            if is_feas:
                st.metric(
                    label="Operational Audit",
                    value="FEASIBLE",
                    delta="All constraints met",
                    delta_color="normal",
                    help="All demand, frequency, speed, and availability rules satisfied.",
                )
            else:
                viols = opt_eval.get("violations", opt_eval.get("constraint_violations", {}))
                active_viols = [k for k, v in viols.items() if v > 0]
                st.metric(
                    label="Operational Audit",
                    value="INFEASIBLE",
                    delta=f"{len(active_viols)} violations",
                    delta_color="inverse",
                    help=f"Active violations: {', '.join(active_viols)}",
                )


def render_plan_insights_card(
    opt_eval: Dict[str, Any],
    best_conv_eval: Dict[str, Any],
    problem: Any,
    carbon_price_ref: float = 80.0,
):
    """
    Renders an executive plain-language Plan Insights card generated from result data.
    """
    insights = generate_plan_insights(
        opt_eval=opt_eval,
        best_conv_eval=best_conv_eval,
        problem=problem,
        carbon_price_ref=carbon_price_ref,
    )

    with st.container(border=True):
        st.markdown("**💡 Plan Insights & Executive Summary**")
        st.write(insights["text_summary"])

        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            abat_val = insights["abatement_cost"]
            st.caption(
                f"**Abatement Cost:** {f'${abat_val:,.1f}/tCO2e' if abat_val is not None else 'N/A (Cost Saving)'}"
            )
        with col_a2:
            st.caption(f"**Clean Propulsion Lanes:** {insights['n_clean_routes']} corridors")
        with col_a3:
            st.caption(f"**Critical Margin:** {insights['weakest_constraint']}")


def render_carbon_intensity_badge(ci_g_tnm: float):
    """
    Renders an A-E style rating badge for the carbon-intensity proxy.
    """
    rating = compute_carbon_intensity_rating(ci_g_tnm)
    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:12px; background:#f8fafc;
            border:1px solid #e2e8f0; border-radius:8px; padding:8px 14px;
        ">
            <span style="
                background:{rating['color']}; color:#ffffff; font-weight:800;
                font-size:18px; width:34px; height:34px; display:inline-flex;
                align-items:center; justify-content:center; border-radius:6px;
            ">{rating['grade']}</span>
            <div>
                <div style="font-size:13px; font-weight:700; color:#1e293b;">
                    Carbon Intensity Rating: {rating['description']}
                </div>
                <div style="font-size:11px; color:#64748b;">
                    Score: <b>{rating['ci_val']} g CO2e / t-nm</b> &bull; <i>{rating['disclaimer']}</i>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_constraints_table(eval_res: Dict[str, Any], problem: Any):
    """
    Renders a clear tabular constraint audit showing PASS/FAIL, actual, limit, and margin.
    """
    route_details = eval_res.get("route_details", {})

    rows = []
    # 1. Total Fleet Vessel Availability
    vessel_types = problem.config.get("vessel_types", {})
    vessels_used = eval_res.get("vessels_used_by_type", {})

    for vt, vt_cfg in vessel_types.items():
        avail = int(vt_cfg.get("fleet_available", 6))
        used = int(vessels_used.get(vt, 0))
        status = "PASS" if used <= avail else "FAIL"
        margin = avail - used
        rows.append({
            "Constraint": f"Fleet Cap ({vt})",
            "Actual": f"{used} vessels",
            "Limit": f"{avail} available",
            "Margin": f"{margin:+d} vessels",
            "Status": status,
        })

    # 2. Demand Satisfaction & Frequency per route
    for r_id, r_info in route_details.items():
        cap = int(round(r_info.get("route_cargo_cap", 0)))
        dem = int(round(r_info.get("annual_demand_teu", 1)))
        dem_status = "PASS" if cap >= dem else "FAIL"
        rows.append({
            "Constraint": f"Demand Coverage ({r_id})",
            "Actual": f"{cap:,} TEU/yr",
            "Limit": f"{dem:,} TEU/yr",
            "Margin": f"{cap - dem:+,} TEU",
            "Status": dem_status,
        })

        freq = r_info.get("sailings_per_week", 0.0)
        min_freq = r_info.get("min_sailings_per_week", r_info.get("min_frequency_wk", 1.0))
        freq_status = "PASS" if freq >= min_freq - 1e-4 else "FAIL"
        rows.append({
            "Constraint": f"Service Frequency ({r_id})",
            "Actual": f"{freq:.2f} /wk",
            "Limit": f"{min_freq:.2f} /wk",
            "Margin": f"{freq - min_freq:+.2f} /wk",
            "Status": freq_status,
        })

    # 3. Supply Cap Ratio per route
    limit_ratio = getattr(problem, "supply_cap_ratio", 2.0)
    if limit_ratio is None:
        limit_ratio = 2.0
    for r_id, r_info in route_details.items():
        ov_ratio = r_info.get("oversupply_ratio", 1.0)
        ov_status = "PASS" if ov_ratio <= limit_ratio + 1e-4 else "FAIL"
        rows.append({
            "Constraint": f"Oversupply Cap ({r_id})",
            "Actual": f"{ov_ratio:.2f}x",
            "Limit": f"{limit_ratio:.2f}x max",
            "Margin": f"{limit_ratio - ov_ratio:+.2f}x",
            "Status": ov_status,
        })

    # 4. Carbon Intensity Cap
    ci_val = eval_res.get("carbon_intensity_g_tnm", 0.0)
    ci_limit = getattr(problem, "ci_cap", getattr(problem, "carbon_intensity_cap", 18.0))
    if ci_limit is None:
        ci_limit = 18.0
    ci_status = "PASS" if ci_val <= ci_limit else "FAIL"
    rows.append({
        "Constraint": "Carbon Intensity Cap",
        "Actual": f"{ci_val:.2f} g/t-nm",
        "Limit": f"{ci_limit:.2f} g/t-nm",
        "Margin": f"{ci_limit - ci_val:+.2f} g/t-nm",
        "Status": ci_status,
    })

    df_c = pd.DataFrame(rows)
    st.dataframe(
        df_c,
        column_config={
            "Status": st.column_config.TextColumn("Audit Status"),
            "Constraint": st.column_config.TextColumn("Regulatory / Operational Rule"),
        },
        hide_index=True,
        width="stretch",
    )


def render_oversupply_chips(eval_res: Dict[str, Any]):
    """
    Renders compact oversupply ratio metrics (capacity / demand) per route.
    """
    route_details = eval_res.get("route_details", {})
    cols = st.columns(len(route_details))
    for i, (r_id, r_info) in enumerate(route_details.items()):
        ov_ratio = r_info.get("oversupply_ratio", 1.0)
        cargo_moved = r_info.get("cargo_actually_moved_teu", 0)
        annual_demand = r_info.get("annual_demand_teu", 1)
        with cols[i]:
            with st.container(border=True):
                st.caption(f"**Route {r_id}**")
                st.markdown(f"**{ov_ratio:.2f}x** ratio")
                st.caption(f"{cargo_moved:,} / {annual_demand:,} TEU")
