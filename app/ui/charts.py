"""
Plotly Chart Builders for Green Fleet Management UI.
Strictly adheres to semantic color tokens, units on axes, and informative hover templates.
Includes Interactive Pareto Trade-off with Knee Point, Q-Bit Heatmaps, and Break-Even Grids.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from app.ui.theme import (
    FUEL_COLORS,
    METRIC_COLORS,
    ALGO_COLORS,
    UI_COLORS,
    get_fuel_color,
    apply_theme_layout,
)


def build_network_map(df_routes: pd.DataFrame, ports_config: Dict[str, Any]) -> go.Figure:
    """
    Renders maritime route corridors on a clean, tile-free Plotly geo canvas.
    Line thickness is proportional to deployed vessels; line color corresponds to fuel type.
    """
    fig = go.Figure()

    # 1. Plot Route Corridors as Lines
    for _, row in df_routes.iterrows():
        orig_id = str(row.get("Origin", "")).lower()
        dest_id = str(row.get("Destination", "")).lower()

        orig_port = ports_config.get(orig_id, {})
        dest_port = ports_config.get(dest_id, {})

        if "lat" in orig_port and "lat" in dest_port:
            lats = [orig_port["lat"], dest_port["lat"]]
            lons = [orig_port["lon"], dest_port["lon"]]

            num_vessels = row.get("Vessels", 1)
            fuel = str(row.get("Fuel", "HFO"))
            speed = row.get("Speed (knots)", 14.0)
            rel = row.get("Reliability (%)", 95.0)
            route_id = row.get("Route ID", "")

            color = get_fuel_color(fuel)
            line_width = max(2.5, min(8.0, num_vessels * 2.2))

            hover_text = (
                f"<b>Route {route_id}</b> ({orig_id.title()} - {dest_id.title()})<br>"
                f"• Deployed Fleet: <b>{num_vessels} vessels</b><br>"
                f"• Fuel System: <b>{fuel}</b><br>"
                f"• Cruising Speed: <b>{speed} knots</b><br>"
                f"• Schedule Reliability: <b>{rel}%</b>"
            )

            fig.add_trace(
                go.Scattergeo(
                    lat=lats,
                    lon=lons,
                    mode="lines",
                    line=dict(width=line_width, color=color),
                    name=f"{route_id}: {fuel}",
                    hoverinfo="text",
                    text=hover_text,
                    showlegend=False,
                )
            )

    # 2. Plot Port Terminals as Markers
    port_lats, port_lons, port_texts, port_names = [], [], [], []
    for p_id, p_info in ports_config.items():
        if "lat" in p_info and "lon" in p_info:
            port_lats.append(p_info["lat"])
            port_lons.append(p_info["lon"])
            port_names.append(p_info.get("name", p_id.title()))
            sp = "Yes" if p_info.get("has_shore_power") else "No"
            port_texts.append(
                f"<b>{p_info.get('name', p_id.title())}</b><br>"
                f"• Country: {p_info.get('country', '')}<br>"
                f"• Shore Power (Cold Ironing): <b>{sp}</b><br>"
                f"• Port Call Fee: ${p_info.get('port_call_fee_usd', 0):,}"
            )

    fig.add_trace(
        go.Scattergeo(
            lat=port_lats,
            lon=port_lons,
            mode="markers+text",
            marker=dict(size=9, color="#0f4c81", symbol="circle", line=dict(width=1.5, color="#ffffff")),
            text=[name.split(" ")[-1].replace("(", "").replace(")", "") for name in port_names],
            textposition="top right",
            textfont=dict(size=10, color="#1e293b"),
            hoverinfo="text",
            hovertext=port_texts,
            name="Ports",
            showlegend=False,
        )
    )

    # Dynamically center and fit to ports if present
    if port_lats and port_lons:
        min_lat, max_lat = min(port_lats), max(port_lats)
        min_lon, max_lon = min(port_lons), max(port_lons)
        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0
        lat_span = max(10.0, (max_lat - min_lat) * 1.3)
        lon_span = max(15.0, (max_lon - min_lon) * 1.3)

        fig.update_geos(
            projection_type="equirectangular",
            showcoastlines=True,
            coastlinecolor="#cbd5e1",
            showland=True,
            landcolor="#f1f5f9",
            showocean=True,
            oceancolor="#ffffff",
            showlakes=False,
            showrivers=False,
            showcountries=True,
            countrycolor="#e2e8f0",
            center=dict(lat=center_lat, lon=center_lon),
            lataxis_range=[center_lat - lat_span / 2.0, center_lat + lat_span / 2.0],
            lonaxis_range=[center_lon - lon_span / 2.0, center_lon + lon_span / 2.0],
        )
    else:
        fig.update_geos(
            projection_type="equirectangular",
            showcoastlines=True,
            coastlinecolor="#cbd5e1",
            showland=True,
            landcolor="#f1f5f9",
            showocean=True,
            oceancolor="#ffffff",
            showcountries=True,
            countrycolor="#e2e8f0",
        )

    apply_theme_layout(
        fig,
        title="Maritime Corridor Network & Terminal Infrastructure",
        height=400,
        margin=dict(l=10, r=10, t=40, b=10),
    )

    return fig


def build_allocation_stacked_bar(df_routes: pd.DataFrame) -> go.Figure:
    """
    Renders stacked bar chart showing vessel deployment and fuel assignments per corridor.
    """
    fig = go.Figure()
    if df_routes.empty:
        return fig

    # Group by route and fuel
    routes = df_routes["Route ID"].unique()
    all_fuels = df_routes["Fuel"].unique()

    for fuel in all_fuels:
        v_counts = []
        for r in routes:
            sub = df_routes[(df_routes["Route ID"] == r) & (df_routes["Fuel"] == fuel)]
            v_counts.append(sub["Vessels"].sum() if not sub.empty else 0)

        fig.add_trace(
            go.Bar(
                x=routes,
                y=v_counts,
                name=str(fuel),
                marker_color=get_fuel_color(str(fuel)),
                hovertemplate="Route %{x}: <b>%{y} vessels</b> (" + str(fuel) + ")<extra></extra>",
            )
        )

    fig.update_layout(barmode="stack")
    apply_theme_layout(
        fig,
        title="Fleet Allocation by Route Corridor",
        xaxis_title="Corridor ID",
        yaxis_title="Vessels Assigned (Count)",
        height=380,
        show_legend=True,
    )
    return fig


def build_emissions_breakdown_chart(eval_res: Dict[str, Any]) -> go.Figure:
    """
    Renders Well-to-Wake emissions breakdown across Tank-to-Wake, Well-to-Tank, and Port Berth.
    """
    emiss = eval_res.get("emissions_breakdown", {})
    ttw = float(emiss.get("ttw_co2e_tonnes", 0.0))
    wtt = float(emiss.get("wtt_co2e_tonnes", 0.0))
    berth = float(emiss.get("berth_co2e_tonnes", 0.0))

    if ttw == 0.0 and wtt == 0.0 and berth == 0.0:
        details = eval_res.get("route_details", {})
        for d in details.values():
            ttw += float(d.get("voyage_ttw_emissions_t", 0.0))
            wtt += float(d.get("voyage_wtt_emissions_t", 0.0))
            berth += float(d.get("berth_emissions_t", 0.0))

    if ttw == 0.0 and wtt == 0.0 and berth == 0.0:
        tot = float(eval_res.get("total_emissions_co2e_tonnes", 0.0))
        if tot > 0:
            ttw = tot * 0.74
            wtt = tot * 0.21
            berth = tot * 0.05

    categories = ["Tank-to-Wake (Combustion)", "Well-to-Tank (Upstream)", "Port Berth (Aux/Shore)"]
    values = [ttw, wtt, berth]
    colors = ["#0f4c81", "#0d9488", "#d97706"]

    fig = go.Figure(
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{v:,.1f} t" for v in values],
            textposition="auto",
            hovertemplate="%{x}: <b>%{y:,.1f} t CO2e</b><extra></extra>",
        )
    )
    apply_theme_layout(
        fig,
        title="Lifecycle GHG Emissions Profile (t CO2e)",
        xaxis_title="Emissions Boundary",
        yaxis_title="Emissions (tonnes CO2e)",
        height=320,
        show_legend=False,
    )
    return fig


def build_cost_breakdown_chart(eval_res: Dict[str, Any]) -> go.Figure:
    """
    Renders cost breakdown across Bunker Fuel, Charter, Port Fees, Carbon Tax, Shore Power.
    """
    costs = eval_res.get("cost_breakdown", {})
    categories = ["Bunker Fuel", "Time Charter", "Port Call Fees", "Carbon Tax", "Shore Power"]
    values = [
        costs.get("fuel_cost_usd", 0.0),
        costs.get("charter_cost_usd", 0.0),
        costs.get("port_fees_usd", 0.0),
        costs.get("carbon_tax_usd", 0.0),
        costs.get("shore_power_cost_usd", 0.0),
    ]
    colors = ["#e63946", "#457b9d", "#64748b", "#2a9d8f", "#7209b7"]

    fig = go.Figure(
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"${int(v):,}" for v in values],
            textposition="auto",
            hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>",
        )
    )
    apply_theme_layout(
        fig,
        title="Annual Fleet Operating Cost Breakdown (USD)",
        xaxis_title="Cost Category",
        yaxis_title="Annual Expenditure ($ USD)",
        height=320,
        show_legend=False,
    )
    return fig


def build_convergence_chart(history: List[float]) -> go.Figure:
    """
    Renders optimization convergence curve.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(history) + 1)),
            y=history,
            mode="lines",
            line=dict(color="#0f4c81", width=2.5),
            name="Best Penalized Fitness",
            hovertemplate="Generation %{x}: Fitness = %{y:.4f}<extra></extra>",
        )
    )
    apply_theme_layout(
        fig,
        title="Algorithmic Convergence Trajectory",
        xaxis_title="Generation / Iteration",
        yaxis_title="Objective Fitness Score (Lower is Better)",
        height=320,
        show_legend=False,
    )
    return fig


def build_pareto_chart(
    pareto_df: pd.DataFrame,
    naive_eval: Optional[Dict[str, Any]] = None,
    best_conv_eval: Optional[Dict[str, Any]] = None,
    knee_point: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """
    Renders Cost vs Emissions trade-off curve with Pareto-optimal frontier,
    distinct naive & best conventional benchmark markers, and highlighted knee point.
    """
    fig = go.Figure()

    if pareto_df.empty:
        return fig

    dominated = pareto_df[~pareto_df.get("is_pareto", False)]
    non_dom = pareto_df[pareto_df.get("is_pareto", False)]

    # 1. Dominated solutions
    if not dominated.empty:
        fig.add_trace(
            go.Scatter(
                x=dominated["Operating Cost ($M)"],
                y=dominated["Lifecycle CO2e (kt)"],
                mode="markers",
                marker=dict(color="#cbd5e1", size=7, opacity=0.7),
                name="Dominated Solutions",
                hovertemplate="Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
            )
        )

    # 2. Pareto Optimal Frontier
    if not non_dom.empty:
        non_dom_sorted = non_dom.sort_values(by="Operating Cost ($M)")
        fig.add_trace(
            go.Scatter(
                x=non_dom_sorted["Operating Cost ($M)"],
                y=non_dom_sorted["Lifecycle CO2e (kt)"],
                mode="lines+markers",
                line=dict(color="#0f4c81", width=2.5),
                marker=dict(color="#2a9d8f", size=9, symbol="circle"),
                name="Pareto Optimal Frontier",
                hovertemplate="<b>Pareto Policy</b><br>Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
            )
        )

    # 3. Naive Baseline Marker
    if naive_eval:
        n_c = naive_eval["total_operating_cost_usd"] / 1e6
        n_e = naive_eval["total_emissions_co2e_tonnes"] / 1000.0
        fig.add_trace(
            go.Scatter(
                x=[n_c],
                y=[n_e],
                mode="markers",
                marker=dict(color="#64748b", size=13, symbol="square"),
                name="Feasible Naive Baseline",
                hovertemplate="<b>Feasible Naive Baseline</b><br>Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
            )
        )

    # 4. Best Conventional Marker
    if best_conv_eval:
        bc_c = best_conv_eval["total_operating_cost_usd"] / 1e6
        bc_e = best_conv_eval["total_emissions_co2e_tonnes"] / 1000.0
        fig.add_trace(
            go.Scatter(
                x=[bc_c],
                y=[bc_e],
                mode="markers",
                marker=dict(color="#f4a261", size=14, symbol="triangle-up"),
                name="Best Conventional Baseline",
                hovertemplate="<b>Best Conventional Baseline</b><br>Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
            )
        )

    # 5. Highlight Knee Point
    if knee_point:
        k_c = knee_point.get("Operating Cost ($M)")
        k_e = knee_point.get("Lifecycle CO2e (kt)")
        if k_c is not None and k_e is not None:
            fig.add_trace(
                go.Scatter(
                    x=[k_c],
                    y=[k_e],
                    mode="markers",
                    marker=dict(color="#e63946", size=16, symbol="star"),
                    name="Knee Point (Best Compromise)",
                    hovertemplate="<b>Knee Point (Max Trade-off Efficiency)</b><br>Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
                )
            )

    apply_theme_layout(
        fig,
        title="Multi-Objective Trade-Off: Operating Cost vs Lifecycle Emissions",
        xaxis_title="Annual Operating Cost ($ Millions USD)",
        yaxis_title="Lifecycle Emissions (Thousand Tonnes CO2e)",
        height=360,
        show_legend=True,
    )
    return fig


def build_qbit_probabilities_heatmap(q_prob_history: List[np.ndarray], max_bits: int = 40) -> go.Figure:
    """
    Renders generation x bit probability heatmap showing Q-bit superposition collapse sin^2(theta).
    """
    if not q_prob_history:
        return go.Figure()

    matrix = np.array(q_prob_history)[:, :max_bits].T  # shape: (n_bits, n_generations)
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=list(range(1, matrix.shape[1] + 1)),
            y=[f"Q-bit {i+1}" for i in range(matrix.shape[0])],
            colorscale="Viridis",
            zmin=0.0,
            zmax=1.0,
            colorbar=dict(title="Probability sin²(θ)"),
            hovertemplate="Bit %{y}<br>Gen %{x}<br>P(1) = %{z:.3f}<extra></extra>",
        )
    )
    apply_theme_layout(
        fig,
        title="Quantum-Inspired Angular Superposition Collapse (Classical Simulation)",
        xaxis_title="Generation",
        yaxis_title="Q-Bit Allele Index",
        height=380,
    )
    return fig


def build_breakeven_heatmap(df_grid: pd.DataFrame) -> go.Figure:
    """
    Renders 2D Break-even sensitivity heatmap over Fuel Price Multiplier x Carbon Price.
    """
    if df_grid.empty:
        return go.Figure()

    pivot = df_grid.pivot(
        index="fuel_price_multiplier",
        columns="carbon_price_usd",
        values="co2e_kt",
    )

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[f"${int(c)}/t" for c in pivot.columns],
            y=[f"{f:.2f}x" for f in pivot.index],
            colorscale="YlGnBu_r",
            colorbar=dict(title="CO2e (kt)"),
            hovertemplate="Fuel Price: %{y}<br>Carbon Tax: %{x}<br>Total Emissions: <b>%{z:.1f} kt CO2e</b><extra></extra>",
        )
    )
    apply_theme_layout(
        fig,
        title="Carbon Tax vs Bunker Price Sensitivity Heatmap (Illustrative)",
        xaxis_title="Carbon Price ($ USD / tCO2e)",
        yaxis_title="Bunker Fuel Price Multiplier",
        height=320,
    )
    return fig
