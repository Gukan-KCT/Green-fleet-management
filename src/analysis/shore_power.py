"""
Shore Power (Cold Ironing) vs Onboard Auxiliary Generator Analysis.

Compares:
1. Conventional auxiliary diesel generators (burning MGO in port)
2. High-Voltage Shore Connection (cold ironing via port electricity grid)
Respects port-specific grid emission factors, electricity tariffs, and cold-ironing infrastructure availability.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

from src.models.physics import load_config, calculate_berth_energy_and_emissions


def calculate_ops_tradeoff(
    port_id: str,
    vessel_type: str = "handymax_feeder",
    berth_hours: Optional[float] = None,
    shore_power_available: Optional[bool] = None,
    electricity_price_usd_per_mwh: Optional[float] = None,
    aux_power_demand_kw: Optional[float] = None,
    connection_efficiency: float = 0.95,
    min_berth_hours: float = 2.0,
    vessel_ops_compatible: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate single-port arrival and berthing Shore Power / Onshore Power Supply (OPS) tradeoff.

    Models:
    Vessel arrives at port
    -> Berthing duration
    -> Hotel/auxiliary energy demand
    -> Shore power availability
    -> Electricity consumption
    -> Shore power cost
    -> Avoided auxiliary engine fuel (MGO)
    -> Avoided emissions (WTW CO2e)

    Inputs:
    - Port: port_id
    - Berthing hours: berth_hours (defaults to port_cfg.berth_hours_avg)
    - Shore power available?: yes/no (defaults to port_cfg.has_shore_power)
    - Electricity price: electricity_price_usd_per_mwh ($/MWh, defaults to port_cfg)
    - Auxiliary power demand: aux_power_demand_kw (defaults to vessel_types[vessel].aux_kw_berth)
    - Shore power connection efficiency: eta (default: 0.95)

    Calculates:
    WITHOUT OPS:
      - Fuel consumption (tonnes MGO)
      - Fuel cost ($)
      - CO2e emissions (tonnes)
    WITH OPS:
      - Electricity consumption (kWh & MWh)
      - Electricity cost ($)
      - CO2e emissions (tonnes)
    DELTAS:
      - Fuel Saved
      - Cost Difference ($ saved)
      - CO2e Avoided
      - Percentage Reduction (%)
    """
    cfg = config or load_config()
    ports_cfg = cfg.get("ports", {})
    vessels_cfg = cfg.get("vessel_types", {})

    p_cfg = dict(ports_cfg.get(port_id, {}))
    if not p_cfg:
        # Fallback port configuration if custom/unlisted
        p_cfg = {
            "name": port_id.title(),
            "has_shore_power": True,
            "grid_ef_tonnes_per_mwh": 0.65,
            "electricity_price_usd_per_mwh": 120.0,
            "berth_hours_avg": 24.0,
        }

    # Override port attributes if explicitly provided by user
    if shore_power_available is not None:
        p_cfg["has_shore_power"] = bool(shore_power_available)
    if electricity_price_usd_per_mwh is not None:
        p_cfg["electricity_price_usd_per_mwh"] = float(electricity_price_usd_per_mwh)

    v_cfg = vessels_cfg.get(vessel_type, {})
    aux_kw = (
        float(aux_power_demand_kw)
        if aux_power_demand_kw is not None
        else float(v_cfg.get("aux_kw_berth", 650.0))
    )
    b_hours = (
        float(berth_hours)
        if berth_hours is not None
        else float(p_cfg.get("berth_hours_avg", 24.0))
    )

    berth_calc = calculate_berth_energy_and_emissions(
        aux_kw=aux_kw,
        berth_hours=b_hours,
        use_shore_power=True,  # Test shore power capability
        port_cfg=p_cfg,
        config=cfg,
        connection_efficiency=connection_efficiency,
        min_berth_hours=min_berth_hours,
        vessel_ops_compatible=vessel_ops_compatible,
    )

    without_ops = berth_calc["without_ops"]
    with_ops = berth_calc["with_ops"]

    # If port has no shore power or vessel is incompatible or berth is too short:
    # Feasibility flag clearly communicates applicability
    ops_feasible = berth_calc["ops_feasible"]

    fuel_saved = without_ops["fuel_tonnes"] if ops_feasible else 0.0
    cost_diff = (without_ops["cost_usd"] - with_ops["electricity_cost_usd"]) if ops_feasible else 0.0
    co2e_avoided = (without_ops["emissions_co2e"] - with_ops["emissions_co2e"]) if ops_feasible else 0.0
    pct_reduction = (
        (co2e_avoided / max(1e-4, without_ops["emissions_co2e"])) * 100.0
        if ops_feasible
        else 0.0
    )

    return {
        "port_id": port_id,
        "port_name": p_cfg.get("name", port_id),
        "vessel_type": vessel_type,
        "vessel_name": v_cfg.get("name", vessel_type),
        "berthing_hours": b_hours,
        "aux_power_demand_kw": aux_kw,
        "hotel_energy_kwh": berth_calc["kwh_required"],
        "hotel_energy_mwh": berth_calc["mwh_required"],
        "shore_power_available": bool(p_cfg.get("has_shore_power", False)),
        "vessel_ops_compatible": vessel_ops_compatible,
        "berth_long_enough": berth_calc["berth_long_enough"],
        "ops_feasible": ops_feasible,
        "connection_efficiency": connection_efficiency,
        "grid_ef_tonnes_per_mwh": float(p_cfg.get("grid_ef_tonnes_per_mwh", 0.65)),
        "electricity_price_usd_per_mwh": float(p_cfg.get("electricity_price_usd_per_mwh", 120.0)),
        # WITHOUT OPS
        "without_ops": {
            "fuel_consumption_tonnes": round(without_ops["fuel_tonnes"], 4),
            "fuel_cost_usd": round(without_ops["cost_usd"], 2),
            "co2e_tonnes": round(without_ops["emissions_co2e"], 4),
        },
        # WITH OPS
        "with_ops": {
            "electricity_consumption_kwh": round(with_ops["electricity_kwh"], 2),
            "electricity_consumption_mwh": round(with_ops["electricity_mwh"], 4),
            "electricity_cost_usd": round(with_ops["electricity_cost_usd"], 2),
            "co2e_tonnes": round(with_ops["emissions_co2e"], 4),
            "feasible": ops_feasible,
        },
        # DELTAS
        "tradeoff": {
            "fuel_saved_tonnes": round(fuel_saved, 4),
            "cost_difference_usd": round(cost_diff, 2),
            "co2e_avoided_tonnes": round(co2e_avoided, 4),
            "percentage_reduction": round(pct_reduction, 2),
        },
        "rejection_reason": (
            None
            if ops_feasible
            else (
                "Port terminal lacks high-voltage shore connection (HVSC) substation"
                if not p_cfg.get("has_shore_power")
                else (
                    "Vessel not equipped with cold-ironing transformer/switchgear"
                    if not vessel_ops_compatible
                    else f"Berthing duration ({b_hours}h) is below minimum safe connection threshold ({min_berth_hours}h)"
                )
            )
        ),
    }


def analyze_shore_power_fleet(
    eval_result: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Perform comparative shore power analysis for an evaluated fleet deployment schedule.

    Calculates:
    - Port-by-port energy consumption, costs, and emissions under:
      (a) Baseline status quo (100% onboard auxiliary engine MGO)
      (b) Maximized shore power (cold ironing at all ports where infrastructure is present)
      (c) Actual deployment schedule choices
    """
    cfg = config or load_config()
    ports_cfg = cfg["ports"]
    routes_cfg = cfg["routes"]
    vessels_cfg = cfg["vessel_types"]

    allocations = eval_result["allocations"]
    speeds = eval_result["speeds"]
    route_keys = list(routes_cfg.keys())
    options = eval_result.get("route_details")

    # Aggregate port calls and auxiliary energy needs per port
    port_calls: Dict[str, float] = {p: 0.0 for p in ports_cfg.keys()}
    port_aux_mwh: Dict[str, float] = {p: 0.0 for p in ports_cfg.keys()}

    days_per_year = float(cfg["general"].get("days_per_year", 350.0))

    # Calculate trips from allocations
    from src.optimization.problem import DEFAULT_CANDIDATE_OPTIONS
    candidate_opts = DEFAULT_CANDIDATE_OPTIONS

    for r_idx, r_key in enumerate(route_keys):
        r_cfg = routes_cfg[r_key]
        dist_nm = float(r_cfg["distance_nm"])
        speed = speeds[r_key]

        orig = r_cfg["origin"]
        dest = r_cfg["destination"]

        b_orig = float(ports_cfg[orig]["berth_hours_avg"])
        b_dest = float(ports_cfg[dest]["berth_hours_avg"])

        rt_hours = (2.0 * dist_nm / speed) + (b_orig + b_dest)
        trips_per_v = (days_per_year * 24.0) / rt_hours

        for o_idx, opt in enumerate(candidate_opts):
            n_v = allocations[o_idx, r_idx]
            if n_v <= 0:
                continue

            ann_trips = n_v * trips_per_v
            v_type = opt["vessel"]
            aux_kw = float(vessels_cfg[v_type]["aux_kw_berth"])

            # Each round trip makes 1 call to origin and 1 call to destination
            port_calls[orig] += ann_trips
            port_calls[dest] += ann_trips

            port_aux_mwh[orig] += (ann_trips * b_orig * aux_kw) / 1000.0
            port_aux_mwh[dest] += (ann_trips * b_dest * aux_kw) / 1000.0

    port_rows = []
    tot_mgo_tonnes_no_sp = 0.0
    tot_cost_no_sp = 0.0
    tot_emiss_no_sp = 0.0

    tot_mgo_tonnes_with_sp = 0.0
    tot_cost_with_sp = 0.0
    tot_emiss_with_sp = 0.0

    sfoc_t_per_mwh = 0.210  # 210 kg MGO per MWh

    for p_key, p_cfg in ports_cfg.items():
        calls = port_calls[p_key]
        mwh = port_aux_mwh[p_key]
        has_sp = bool(p_cfg.get("has_shore_power", False))

        # Scenario A: 100% Onboard Generator (MGO)
        mgo_tonnes = mwh * sfoc_t_per_mwh
        mgo_price = float(cfg["fuels"]["MGO"]["price_usd_per_tonne"]["default"])
        cost_mgo = mgo_tonnes * mgo_price
        # MGO emissions (TtW 3.206 + WtT 0.65 = 3.856 t CO2e/t)
        emiss_mgo = mgo_tonnes * (3.206 + 0.65)

        tot_mgo_tonnes_no_sp += mgo_tonnes
        tot_cost_no_sp += cost_mgo
        tot_emiss_no_sp += emiss_mgo

        # Scenario B: Maximized Shore Power (where available)
        if has_sp:
            mgo_sp = 0.0
            tariff = float(p_cfg.get("electricity_price_usd_per_mwh", 120.0))
            grid_ef = float(p_cfg.get("grid_ef_tonnes_per_mwh", 0.65))
            cost_sp = mwh * tariff
            emiss_sp = mwh * grid_ef
        else:
            # Must run generator
            mgo_sp = mgo_tonnes
            cost_sp = cost_mgo
            emiss_sp = emiss_mgo

        tot_mgo_tonnes_with_sp += mgo_sp
        tot_cost_with_sp += cost_sp
        tot_emiss_with_sp += emiss_sp

        co2_avoided = emiss_mgo - emiss_sp
        cost_savings = cost_mgo - cost_sp

        port_rows.append(
            {
                "port_id": p_key,
                "port_name": p_cfg["name"],
                "has_shore_power": has_sp,
                "annual_port_calls": round(calls, 1),
                "aux_energy_mwh": round(mwh, 1),
                "grid_ef_tonnes_mwh": float(p_cfg.get("grid_ef_tonnes_per_mwh", 0.65)),
                "no_sp_mgo_tonnes": round(mgo_tonnes, 1),
                "no_sp_cost_usd": round(cost_mgo, 0),
                "no_sp_emissions_co2e": round(emiss_mgo, 1),
                "with_sp_mgo_tonnes": round(mgo_sp, 1),
                "with_sp_cost_usd": round(cost_sp, 0),
                "with_sp_emissions_co2e": round(emiss_sp, 1),
                "co2_avoided_tonnes": round(co2_avoided, 1),
                "co2_reduction_pct": round((co2_avoided / max(1e-4, emiss_mgo)) * 100.0, 1) if has_sp else 0.0,
                "cost_savings_usd": round(cost_savings, 0),
            }
        )

    df_ports = pd.DataFrame(port_rows)

    tot_co2_avoided = tot_emiss_no_sp - tot_emiss_with_sp
    tot_fuel_saved = tot_mgo_tonnes_no_sp - tot_mgo_tonnes_with_sp
    tot_cost_savings = tot_cost_no_sp - tot_cost_with_sp

    summary = {
        "annual_port_calls_total": float(sum(port_calls.values())),
        "annual_aux_energy_mwh_total": float(sum(port_aux_mwh.values())),
        "without_shore_power": {
            "mgo_fuel_tonnes": round(tot_mgo_tonnes_no_sp, 1),
            "operating_cost_usd": round(tot_cost_no_sp, 0),
            "emissions_co2e_tonnes": round(tot_emiss_no_sp, 1),
        },
        "with_max_shore_power": {
            "mgo_fuel_tonnes": round(tot_mgo_tonnes_with_sp, 1),
            "operating_cost_usd": round(tot_cost_with_sp, 0),
            "emissions_co2e_tonnes": round(tot_emiss_with_sp, 1),
        },
        "net_benefit": {
            "fuel_saved_tonnes": round(tot_fuel_saved, 1),
            "fuel_reduction_pct": round((tot_fuel_saved / max(1e-4, tot_mgo_tonnes_no_sp)) * 100.0, 1),
            "co2_avoided_tonnes": round(tot_co2_avoided, 1),
            "co2_reduction_pct": round((tot_co2_avoided / max(1e-4, tot_emiss_no_sp)) * 100.0, 1),
            "cost_savings_usd": round(tot_cost_savings, 0),
        },
    }

    return {
        "port_breakdown": df_ports,
        "summary": summary,
    }
