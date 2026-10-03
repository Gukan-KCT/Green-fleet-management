"""
Alternative Marine Fuel Comparison Analysis.

Compares maritime fuels across:
1. Volumetric/mass energy density (LHV in MJ/kg)
2. Fuel consumption mass (tonnes) via energy equivalence
3. Well-to-Wake lifecycle emissions (Tank-to-Wake combustion + Well-to-Tank upstream pathways)
4. Unburned slip penalties (methane slip for LNG, N2O slip for ammonia)
5. Fuel procurement costs ($ USD)
6. Usable cargo capacity penalties (volumetric tank loss)
7. Bunkering port feasibility

Fuels: Conventional (HFO, MGO), LNG, Methanol, Ammonia, Liquid Hydrogen.
Production Pathways: Fossil, Grey (fossil without CCS), Blue (fossil with CCS), Green (renewable e-fuel / electrolysis).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

from src.models.physics import (
    load_config,
    calculate_leg_fuel_conventional,
    calculate_alternative_fuel_mass,
    calculate_fuel_energy_gj,
    calculate_emissions,
    get_fuel_price_usd_per_tonne,
    calculate_usable_capacity_teu,
)


def compare_fuels_for_voyage(
    vessel_key: str = "handymax_feeder",
    route_key: str = "R1",
    speed_knots: float = 14.5,
    cargo_load_tonnes: float = 16000.0,
    pathway_choices: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Compare all candidate fuels for a standard single voyage leg.

    Args:
        vessel_key: Vessel type from config.
        route_key: Route ID from config.
        speed_knots: Cruising speed in knots.
        cargo_load_tonnes: Cargo payload in tonnes.
        pathway_choices: Optional mapping of fuel_type -> pathway ('green', 'blue', 'grey').
        config: System configuration dictionary.

    Returns:
        DataFrame with detailed techno-economic and environmental metrics per fuel.
    """
    cfg = config or load_config()
    v_cfg = cfg["vessel_types"][vessel_key]
    r_cfg = cfg["routes"][route_key]
    distance_nm = float(r_cfg["distance_nm"])
    weather = float(r_cfg.get("weather_severity", 0.3))
    k_w = float(cfg["general"].get("weather_penalty_k_w", 0.35))

    # Baseline HFO consumption
    base_fuel_hfo, leg_days = calculate_leg_fuel_conventional(
        vessel_cfg=v_cfg,
        speed_knots=speed_knots,
        distance_nm=distance_nm,
        cargo_load_tonnes=cargo_load_tonnes,
        weather_severity=weather,
        k_w=k_w,
    )

    orig_port = cfg["ports"][r_cfg["origin"]]
    dest_port = cfg["ports"][r_cfg["destination"]]

    pathways = pathway_choices or {
        "Methanol": "green",
        "Ammonia": "green",
        "Hydrogen": "green",
    }

    fuel_keys = ["HFO", "MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
    rows = []

    for fuel in fuel_keys:
        f_cfg = cfg["fuels"][fuel]
        pathway = pathways.get(fuel, f_cfg.get("default_pathway", "default"))

        # Energy equivalence
        mass_tonnes = calculate_alternative_fuel_mass(base_fuel_hfo, fuel, cfg)
        energy_gj = calculate_fuel_energy_gj(mass_tonnes, fuel, cfg)

        # Emissions breakdown
        emiss = calculate_emissions(mass_tonnes, fuel, pathway=pathway, config=cfg)

        # Fuel cost
        price_per_t = get_fuel_price_usd_per_tonne(fuel, pathway=pathway, config=cfg)
        fuel_cost = mass_tonnes * price_per_t

        # Capacity penalty
        nom_teu = float(v_cfg["capacity_teu"])
        usable_teu = calculate_usable_capacity_teu(nom_teu, fuel, cfg)
        penalty_pct = float(f_cfg.get("capacity_penalty_pct", 0.0))

        # Port bunkering feasibility
        orig_supp = fuel in orig_port.get("supported_fuels", [])
        dest_supp = fuel in dest_port.get("supported_fuels", [])
        bunkering_feasible = orig_supp or dest_supp

        rows.append(
            {
                "fuel_type": fuel,
                "display_name": f_cfg["name"],
                "pathway": pathway,
                "lhv_mj_kg": float(f_cfg["lhv_mj_kg"]),
                "fuel_mass_tonnes": round(mass_tonnes, 2),
                "energy_gj": round(energy_gj, 1),
                "fuel_price_usd_tonne": round(price_per_t, 1),
                "fuel_cost_usd": round(fuel_cost, 0),
                "ttw_co2e_tonnes": round(emiss["tank_to_wake"], 2),
                "wtt_co2e_tonnes": round(emiss["well_to_tank"], 2),
                "slip_co2e_tonnes": round(emiss["slip"], 2),
                "lifecycle_co2e_tonnes": round(emiss["total_co2e"], 2),
                "ghg_intensity_gco2e_mj": round(
                    (emiss["total_co2e"] * 1e6) / max(1.0, energy_gj * 1000.0), 1
                ),
                "cargo_loss_pct": penalty_pct,
                "usable_teu": round(usable_teu, 0),
                "bunkering_feasible": bunkering_feasible,
            }
        )

    return pd.DataFrame(rows)
