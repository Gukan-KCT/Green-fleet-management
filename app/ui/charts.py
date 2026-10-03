"""
Plotly Chart Builders for Green Fleet Management UI.
Strictly adheres to semantic color tokens, units on axes, and informative hover templates.
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

    fig.update_layout(
        geo=dict(
            scope="asia",
            center=dict(lat=12.0, lon=85.0),
            projection_scale=2.2,
            showland=True,
            landcolor="#f1f5f9",
            countrycolor="#cbd5e1",
            showocean=True,
            oceancolor="#e2e8f0",
            showcoastlines=True,
            coastlinecolor="#94a3b8",
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        height=370,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_allocation_stacked_bar(df_routes: pd.DataFrame) -> go.Figure:
    """
    Renders stacked bar of vessels deployed per corridor, colored by fuel type.
    """
    fig = go.Figure()

    if df_routes.empty:
        return fig

    # Group by Fuel type for clean semantic color coding and compact legend
    fuels = df_routes["Fuel"].unique()
    for fuel in fuels:
        sub = df_routes[df_routes["Fuel"] == fuel]
        color = get_fuel_color(str(fuel))

        hover_lines = []
        for _, row in sub.iterrows():
            r_name = row.get("Name", row["Route ID"])
            hover_lines.append(
                f"<b>{row['Route ID']}</b> ({r_name})<br>"
                f"Fleet: <b>{row['Vessels']} vessels</b><br>"
                f"Fuel: <b>{fuel}</b><br>"
                f"Allocation: {row.get('Option', '')}<br>"
                f"Speed: {row.get('Speed (knots)', 14.0)} kn<br>"
                f"Reliability: {row.get('Reliability (%)', 95.0)}%"
            )

        fig.add_trace(
            go.Bar(
                x=sub["Route ID"],
                y=sub["Vessels"],
                name=str(fuel),
                marker_color=color,
                text=sub["Vessels"].apply(lambda v: f"{v} vsl"),
                textposition="auto",
                hoverinfo="text",
                hovertext=hover_lines,
            )
        )

    fig.update_layout(barmode="stack")
    apply_theme_layout(
        fig,
        title=None,
        xaxis_title="Shipping Corridor",
        yaxis_title="Vessels Assigned (Count)",
        height=320,
        show_legend=len(fuels) > 1,
    )
    return fig


def build_emissions_breakdown_chart(eval_res: Dict[str, Any]) -> go.Figure:
    """
    Renders well-to-wake lifecycle emissions breakdown (Tank-to-Wake, Well-to-Tank, Berth).
    """
    route_details = eval_res.get("route_details", {})
    ttw_total = sum(r.get("voyage_ttw_emissions_t", 0.0) for r in route_details.values())
    wtt_total = sum(r.get("voyage_wtt_emissions_t", 0.0) for r in route_details.values())
    berth_total = sum(r.get("berth_emissions_t", 0.0) for r in route_details.values())

    categories = ["Tank-to-Wake (Combustion)", "Well-to-Tank (Upstream)", "Port Berth (Aux/Shore)"]
    values = [round(ttw_total, 1), round(wtt_total, 1), round(berth_total, 1)]
    colors = ["#2b2d42", "#2a9d8f", "#457b9d"]

    fig = go.Figure(
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{v:,} t" for v in values],
            textposition="auto",
            hovertemplate="%{x}: <b>%{y:,} tonnes CO2e</b><extra></extra>",
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


def build_pareto_chart(pareto_df: pd.DataFrame) -> go.Figure:
    """
    Renders Cost vs Emissions trade-off curve with Pareto-optimal non-dominated frontier.
    """
    fig = go.Figure()

    if pareto_df.empty:
        return fig

    dominated = pareto_df[~pareto_df.get("is_pareto", False)]
    non_dom = pareto_df[pareto_df.get("is_pareto", False)]

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

    if not non_dom.empty:
        non_dom_sorted = non_dom.sort_values(by="Operating Cost ($M)")
        fig.add_trace(
            go.Scatter(
                x=non_dom_sorted["Operating Cost ($M)"],
                y=non_dom_sorted["Lifecycle CO2e (kt)"],
                mode="lines+markers",
                line=dict(color="#0f4c81", width=2.5),
                marker=dict(color="#e63946", size=10, symbol="diamond"),
                name="Pareto Optimal Frontier",
                hovertemplate="<b>Pareto Optimal</b><br>Cost: $%{x:.2f}M<br>CO2e: %{y:.2f} kt<extra></extra>",
            )
        )

    apply_theme_layout(
        fig,
        title="Multi-Objective Trade-Off: Operating Cost vs Lifecycle Emissions",
        xaxis_title="Annual Operating Cost ($ Millions USD)",
        yaxis_title="Lifecycle Emissions (Thousand Tonnes CO2e)",
        height=320,
        show_legend=True,
    )
    return fig
