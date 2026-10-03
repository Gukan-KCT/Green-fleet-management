"""
Network Builder - Interactive Maritime Port & Route Topology Workspace.
Define custom ports, routes, demand, sea conditions, and export/import topologies.
"""

from __future__ import annotations
import sys
import json
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Network Builder | Green Fleet",
    page_icon="🌐",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.charts import build_network_map
from app.ui.css import inject_css
from dataclasses import asdict
from src.models.physics import load_config
from src.models.network import (
    Network,
    PortDefinition,
    RouteDefinition,
    get_demo_network,
    load_ports_catalog,
    calculate_haversine_distance_nm,
    DEFAULT_CANDIDATE_OPTIONS,
)


inject_css()
render_top_strip(
    title="Maritime Network Builder",
    subtitle="Define terminal infrastructure, customize shipping corridors, and manage custom fleet network topologies.",
)

cfg = load_config()
general_cfg = cfg.get("general", {})
detour_factor = float(general_cfg.get("detour_factor", 1.15))
max_interactive_routes = int(general_cfg.get("max_interactive_routes", 8))
sea_map = general_cfg.get("sea_conditions_map", {"calm": 0.15, "moderate": 0.30, "rough": 0.45})

# Initialize Active Network in Session State
if "active_network" not in st.session_state:
    st.session_state["active_network"] = get_demo_network()

net: Network = st.session_state["active_network"]
catalog_ports = load_ports_catalog()

# Top Toolbar: Presets & Actions
c_actions, c_stats = st.columns([3, 2])
with c_actions:
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    if col_a1.button("↺ Reset to Demo", help="Restore the default South Asian Feeder demo network", width="stretch"):
        st.session_state["active_network"] = get_demo_network()
        st.success("Network reset to default South Asia Feeder baseline.")
        st.rerun()

    # JSON Export
    export_json = json.dumps(net.to_dict(), indent=2)
    col_a2.download_button(
        label="⭳ Export (JSON)",
        data=export_json,
        file_name=f"green_fleet_network_{net.name.lower().replace(' ', '_')}.json",
        mime="application/json",
        width="stretch",
    )

    # JSON Import Uploader Expander
    with col_a3:
        with st.popover("⭱ Import", use_container_width=True):
            uploaded_file = st.file_uploader("Upload Network JSON", type=["json"])
            if uploaded_file is not None:
                try:
                    data = json.load(uploaded_file)
                    imported_net, errs = Network.from_dict(data)
                    if errs:
                        st.error("Validation failed:\n" + "\n".join(f"• {e}" for e in errs))
                    else:
                        st.session_state["active_network"] = imported_net
                        st.success(f"Successfully loaded '{imported_net.name}'!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Failed to read JSON: {e}")

    with col_a4:
        if st.button("✈ Switch to Planner", type="primary", width="stretch"):
            st.switch_page("Home.py")

with c_stats:
    st.markdown(
        f"""
        <div style="background:var(--slate-100, #f1f5f9); padding:8px 14px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; border:1px solid var(--slate-200, #e2e8f0);">
          <div>
            <div style="font-size:11px; color:#64748b; font-weight:700; text-transform:uppercase;">Topology Status</div>
            <div style="font-size:14px; font-weight:700; color:#0f172a;">{net.name}</div>
          </div>
          <div style="text-align:right;">
            <span style="font-size:13px; font-weight:700; color:#0f4c81;">{len(net.ports)} Ports</span> &nbsp;|&nbsp;
            <span style="font-size:13px; font-weight:700; color:#0d9488;">{len(net.routes)} / {max_interactive_routes} Routes</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# Layout: Left Tabs (Builder & Ports) | Right (Interactive Map & Validation)
col_left, col_right = st.columns([3, 2])

with col_left:
    tab_routes, tab_add_route, tab_add_port, tab_catalog = st.tabs([
        "📍 Active Routes", "➕ Create Corridor", "⚓ Add Custom Port", "📖 Port Catalog"
    ])

    # --- TAB 1: ACTIVE ROUTES TABLE ---
    with tab_routes:
        st.markdown("##### Configured Shipping Routes")
        if not net.routes:
            st.info("No active shipping corridors. Create one in the 'Create Corridor' tab.")
        else:
            routes_data = []
            for r_id, r in net.routes.items():
                orig_name = net.ports[r.origin].name if r.origin in net.ports else r.origin
                dest_name = net.ports[r.destination].name if r.destination in net.ports else r.destination
                ref_days = round(r.distance_nm / (14.0 * 24.0), 1)

                routes_data.append({
                    "ID": r_id,
                    "Name": r.name,
                    "Origin": orig_name,
                    "Destination": dest_name,
                    "Demand (TEU/yr)": r.annual_demand_teu,
                    "Distance (nm)": f"{r.distance_nm:.1f} (approx)",
                    "Sea Conditions": r.sea_conditions,
                    "Est Transit (14kn)": f"{ref_days} d",
                })

            df_routes_display = pd.DataFrame(routes_data)
            st.dataframe(df_routes_display, hide_index=True, use_container_width=True)

            # Route deletion controls
            st.markdown("###### Manage Routes")
            del_cols = st.columns([3, 1])
            route_to_del = del_cols[0].selectbox("Select Route to Remove", list(net.routes.keys()), key="sb_del_route")
            if del_cols[1].button("Delete Route", type="secondary", width="stretch"):
                if len(net.routes) <= 1:
                    st.warning("Network must have at least 1 active route for optimization.")
                else:
                    net.routes.pop(route_to_del, None)
                    net.is_demo = False
                    net.name = "Custom Fleet Network"
                    st.session_state["active_network"] = net
                    st.rerun()

    # --- TAB 2: CREATE CORRIDOR ---
    with tab_add_route:
        st.markdown("##### Connect Two Ports into a Commercial Corridor")
        if len(net.routes) >= max_interactive_routes:
            st.warning(f"Maximum limit of {max_interactive_routes} interactive routes reached.")
        else:
            port_opts = {pid: p.name for pid, p in net.ports.items()}

            c_o, c_d = st.columns(2)
            orig_sel = c_o.selectbox("Origin Port", list(port_opts.keys()), format_func=lambda x: port_opts[x], key="cr_orig")
            dest_sel = c_d.selectbox("Destination Port", list(port_opts.keys()), index=min(1, len(port_opts)-1), format_func=lambda x: port_opts[x], key="cr_dest")

            # Calculate default distance using Haversine + Detour factor
            p_orig = net.ports.get(orig_sel)
            p_dest = net.ports.get(dest_sel)
            auto_dist = 500.0
            if p_orig and p_dest and orig_sel != dest_sel:
                auto_dist = calculate_haversine_distance_nm(p_orig.lat, p_orig.lon, p_dest.lat, p_dest.lon, detour_factor)

            c_dem, c_sea = st.columns(2)
            demand_in = c_dem.number_input("Annual Cargo Demand (TEU/year)", min_value=1000, max_value=2000000, value=100000, step=10000)
            sea_cond_in = c_sea.selectbox("Sea Conditions & Weather Severity", ["Calm", "Moderate", "Rough"], index=1)

            c_dist, c_speed = st.columns(2)
            dist_override = c_dist.number_input(
                "Distance (approx nautical miles, not real shipping lane)",
                min_value=10.0,
                max_value=25000.0,
                value=float(auto_dist),
                step=25.0,
                help="Defaults to Great-Circle (Haversine) distance multiplied by illustrative 1.15x detour factor.",
            )
            speed_cap_in = c_speed.slider("Corridor Speed Limit (knots)", 10.0, 22.0, 18.0, 0.5)

            ref_transit_days = round(dist_override / (14.0 * 24.0), 1)
            st.caption(f"ℹ️ **Approximate Transit Time at 14.0 knots:** ~{ref_transit_days} days per one-way leg.")

            if st.button("➕ Add Corridor to Network", type="primary", width="stretch"):
                if orig_sel == dest_sel:
                    st.error("Origin and Destination cannot be the same port.")
                else:
                    new_rid = f"R{len(net.routes) + 1}"
                    # Check for duplicate pair
                    dup = any(r.origin == orig_sel and r.destination == dest_sel for r in net.routes.values())
                    if dup:
                        st.warning(f"A route between {p_orig.name} and {p_dest.name} already exists.")
                    else:
                        w_factor = sea_map.get(sea_cond_in.lower(), 0.30)
                        new_r = RouteDefinition(
                            id=new_rid,
                            name=f"{p_orig.name.split('(')[0].strip()} - {p_dest.name.split('(')[0].strip()}",
                            origin=orig_sel,
                            destination=dest_sel,
                            annual_demand_teu=int(demand_in),
                            distance_nm=float(dist_override),
                            sea_conditions=sea_cond_in,
                            weather_severity=float(w_factor),
                            speed_cap_knots=float(speed_cap_in),
                            is_distance_overridden=(dist_override != auto_dist),
                        )
                        net.routes[new_rid] = new_r
                        net.is_demo = False
                        net.name = "Custom Fleet Network"
                        st.session_state["active_network"] = net
                        st.success(f"Route {new_rid} successfully added!")
                        st.rerun()

    # --- TAB 3: ADD CUSTOM PORT ---
    with tab_add_port:
        st.markdown("##### Add New Maritime Terminal")
        p_name = st.text_input("Port Name", "Port of Colombo New Terminal")
        p_country = st.text_input("Country", "Sri Lanka")
        c_lat, c_lon = st.columns(2)
        p_lat = c_lat.number_input("Latitude (-90 to +90)", min_value=-90.0, max_value=90.0, value=6.95, step=0.01)
        p_lon = c_lon.number_input("Longitude (-180 to +180)", min_value=-180.0, max_value=180.0, value=79.85, step=0.01)
        st.caption("Disclaimer: Coordinates are approximate centroids for illustrative modeling.")

        c_sp, c_fuels = st.columns(2)
        p_sp = c_sp.checkbox("Shore Power (Cold Ironing) Available", value=False)
        p_fuels = c_fuels.multiselect("Bunkering Fuels Supported", ["HFO", "MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"], default=["HFO", "MGO"])

        if st.button("➕ Register Port into Network", width="stretch"):
            pid = p_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")[:20]
            if pid in net.ports:
                pid = f"{pid}_{len(net.ports)+1}"

            new_port = PortDefinition(
                id=pid,
                name=p_name,
                country=p_country,
                lat=float(p_lat),
                lon=float(p_lon),
                has_shore_power=p_sp,
                supported_fuels=p_fuels if p_fuels else ["HFO"],
                coordinates_note="approximate, verify",
            )
            v_errs = new_port.validate()
            if v_errs:
                st.error("\n".join(f"• {e}" for e in v_errs))
            else:
                net.ports[pid] = new_port
                net.is_demo = False
                net.name = "Custom Fleet Network"
                st.session_state["active_network"] = net
                st.success(f"Port '{p_name}' successfully added to network!")
                st.rerun()

    # --- TAB 4: PORT CATALOG ---
    with tab_catalog:
        st.markdown("##### Global Port Catalog (26+ Major Terminals)")
        st.caption("Select any catalog terminal to quickly import into your active topology. Non-demo catalog ports default to: No shore power, HFO/MGO bunkering only.")

        catalog_unadded = {k: v for k, v in catalog_ports.items() if k not in net.ports}
        if not catalog_unadded:
            st.info("All catalog ports are already in the active network.")
        else:
            cat_choice = st.selectbox("Select Catalog Port to Import", list(catalog_unadded.keys()), format_func=lambda x: f"{catalog_unadded[x]['name']} ({catalog_unadded[x].get('country', '')})")
            p_cat = catalog_unadded[cat_choice]
            st.markdown(f"**Location:** Lat `{p_cat['lat']}`, Lon `{p_cat['lon']}` ({p_cat.get('coordinates_note', 'approximate')})")
            st.markdown(f"**Bunkering:** `{p_cat.get('supported_fuels', ['HFO', 'MGO'])}` | **Shore Power:** `{'Yes' if p_cat.get('has_shore_power') else 'No'}`")

            if st.button("📥 Import Catalog Port into Active Network", width="stretch"):
                net.ports[cat_choice] = PortDefinition(
                    id=cat_choice,
                    name=p_cat["name"],
                    country=p_cat.get("country", "Custom"),
                    lat=float(p_cat["lat"]),
                    lon=float(p_cat["lon"]),
                    has_shore_power=bool(p_cat.get("has_shore_power", False)),
                    supported_fuels=list(p_cat.get("supported_fuels", ["HFO", "MGO"])),
                    grid_ef_tonnes_per_mwh=float(p_cat.get("grid_ef_tonnes_per_mwh", 0.65)),
                    electricity_price_usd_per_mwh=float(p_cat.get("electricity_price_usd_per_mwh", 125.0)),
                    port_call_fee_usd=float(p_cat.get("port_call_fee_usd", 6500.0)),
                    berth_hours_avg=float(p_cat.get("berth_hours_avg", 24.0)),
                    coordinates_note=p_cat.get("coordinates_note", "approximate, verify"),
                )
                net.is_demo = False
                net.name = "Custom Fleet Network"
                st.session_state["active_network"] = net
                st.success(f"Port '{p_cat['name']}' imported!")
                st.rerun()

with col_right:
    st.markdown("##### Live Network Geometry & Terminal Map")
    # Build routes dataframe for the map
    map_rows = []
    for r_k, r in net.routes.items():
        map_rows.append({
            "Route ID": r_k,
            "Origin": r.origin,
            "Destination": r.destination,
            "Vessels": 2,
            "Fuel": "HFO",
            "Speed (knots)": 14.0,
            "Reliability (%)": 95.0,
        })
    df_map = pd.DataFrame(map_rows)

    # Ports dict for map
    ports_map_dict = {pid: asdict(p) for pid, p in net.ports.items()}
    fig_map = build_network_map(df_map, ports_map_dict)
    st.plotly_chart(fig_map, use_container_width=True)

    # Runtime Estimation & Sizing Alert
    num_opts = len(DEFAULT_CANDIDATE_OPTIONS)
    num_routes = len(net.routes)
    num_ports = len(net.ports)
    n_bits = (2 * num_opts * num_routes) + (3 * num_routes) + num_ports
    est_runtime_s = round(num_routes * 1.8, 1)

    st.markdown("###### Problem Dimension & Estimated Runtime")
    c_d1, c_d2 = st.columns(2)
    c_d1.metric("Chromosome Size", f"{n_bits} bits")
    c_d2.metric("Est. Runtime (CPU)", f"~{est_runtime_s} s")

    if est_runtime_s > 60.0:
        st.warning("⚠️ High problem scale: Optimization run time is estimated to exceed 60 seconds.")
    else:
        st.caption("✅ Fast interactive scale: Optimization will execute well under the 60-second limit.")
