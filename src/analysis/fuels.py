"""
Alternative Marine Fuel Parameter Modeling & Techno-Economic Assessment.

Defines structured parameter models for all supported maritime fuels:
1. Conventional Marine Fuel (HFO, MGO)
2. Liquefied Natural Gas (LNG)
3. Methanol (CH3OH)
4. Ammonia (NH3)
5. Liquid Hydrogen (LH2)

Each fuel parameter is explicitly categorized with data source & assumption tags:
- 'Real / Publicly Sourced' (IMO 4th GHG Study, ISO 8217, DNV, MEPC)
- 'Project Assumption' (IRENA 2025-2030 cost curves, port infrastructure surveys)
- 'Synthetic / Illustrative' (Prototype feeder demonstration parameters)
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
    FuelEmissionProfile,
    get_fuel_emission_profile,
    list_all_emission_profiles,
)


# Vessel-Fuel Compatibility Matrix
VESSEL_FUEL_COMPATIBILITY: Dict[str, List[str]] = {
    "small_feeder": ["HFO", "MGO", "LNG", "Methanol", "Hydrogen"],
    "handymax_feeder": ["HFO", "MGO", "LNG", "Methanol", "Ammonia"],
    "sub_panamax_feeder": ["HFO", "MGO", "LNG", "Methanol", "Ammonia"],
    "panamax_feeder": ["HFO", "MGO", "LNG", "Methanol", "Ammonia"],
}

# Structured Parameter Specifications with Source/Assumption Provenance
FUEL_STRUCTURED_PARAMETERS: Dict[str, Dict[str, Any]] = {
    "HFO": {
        "fuel_key": "HFO",
        "fuel_name": "Heavy Fuel Oil (HFO)",
        "fuel_category": "Conventional Residual Marine Fuel",
        "energy_content_mj_kg": 40.2,
        "energy_density_label": "40.2 MJ/kg (LHV)",
        "engine_efficiency_ratio": 1.0,
        "price_usd_per_tonne": {"default": 550.0, "fossil": 550.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 0.0,
            "storage_type": "Standard double-bottom uninsulated tanks (ambient/heated)",
            "temperature_c": 45.0,
            "pressure_bar": 1.0,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 3.114,
            "ef_well_to_tank": {"default": 0.58, "fossil": 0.58},
            "slip_factor_co2e_per_tonne": 0.0,
            "total_wtw_co2e_per_tonne": {"default": 3.694, "fossil": 3.694},
        },
        "availability_assumption": "Universal: 100% commercial bunkering port availability globally",
        "vessel_compatibility": ["small_feeder", "handymax_feeder", "sub_panamax_feeder", "panamax_feeder"],
        "operational_constraints": [
            "High sulfur requires exhaust gas cleaning (scrubber) or low-sulfur ECA switch",
            "High carbon intensity under IMO Carbon Intensity Indicator (CII)",
            "Requires fuel pre-heating and centrifugal purification on board",
        ],
        "co2e_factor": 3.694,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (IMO 4th GHG Study 2020 / ISO 8217: 40.2 MJ/kg)",
            "prices": "Project Assumption (Global bunker index proxy: $550/t)",
            "emissions": "Real / Publicly Sourced (IMO MEPC.308(73) & MEPC 80 LCA: 3.114 t TtW + 0.58 t WtT)",
            "storage": "Real / Publicly Sourced (Naval Architecture Baseline: 0.0% slot loss)",
            "availability": "Real / Publicly Sourced (Global Marine Port Bunkering Catalog)",
        },
    },
    "MGO": {
        "fuel_key": "MGO",
        "fuel_name": "Marine Gas Oil (MGO)",
        "fuel_category": "Low-Sulfur Distillate Fuel",
        "energy_content_mj_kg": 42.7,
        "energy_density_label": "42.7 MJ/kg (LHV)",
        "engine_efficiency_ratio": 1.0,
        "price_usd_per_tonne": {"default": 780.0, "fossil": 780.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 0.0,
            "storage_type": "Standard distillate tanks (ambient)",
            "temperature_c": 20.0,
            "pressure_bar": 1.0,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 3.206,
            "ef_well_to_tank": {"default": 0.65, "fossil": 0.65},
            "slip_factor_co2e_per_tonne": 0.0,
            "total_wtw_co2e_per_tonne": {"default": 3.856, "fossil": 3.856},
        },
        "availability_assumption": "Universal: 100% commercial bunkering port availability globally",
        "vessel_compatibility": ["small_feeder", "handymax_feeder", "sub_panamax_feeder", "panamax_feeder"],
        "operational_constraints": [
            "Premium fuel cost over residual fuels",
            "Low viscosity requires fuel cooler in tropical sea routes",
            "Standard auxiliary engine fuel in port without shore power",
        ],
        "co2e_factor": 3.856,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (IMO 4th GHG Study 2020: 42.7 MJ/kg)",
            "prices": "Project Assumption (Bunker Index Benchmark: $780/t)",
            "emissions": "Real / Publicly Sourced (IMO MEPC.308(73): 3.206 t TtW + 0.65 t WtT)",
            "storage": "Real / Publicly Sourced (Standard Distillate Tank)",
            "availability": "Real / Publicly Sourced (Universal Port Supply)",
        },
    },
    "LNG": {
        "fuel_key": "LNG",
        "fuel_name": "Liquefied Natural Gas (LNG)",
        "fuel_category": "Cryogenic Transition Fossil Fuel",
        "energy_content_mj_kg": 48.0,
        "energy_density_label": "48.0 MJ/kg (LHV)",
        "engine_efficiency_ratio": 1.03,
        "price_usd_per_tonne": {"default": 720.0, "fossil": 720.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 3.0,
            "storage_type": "Cryogenic Type-C vacuum-insulated tanks (-162°C)",
            "temperature_c": -162.0,
            "pressure_bar": 4.0,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 2.750,
            "ef_well_to_tank": {"default": 0.82, "fossil": 0.82},
            "slip_factor_co2e_per_tonne": 0.15,
            "total_wtw_co2e_per_tonne": {"default": 3.720, "fossil": 3.720},
        },
        "availability_assumption": "Established: ~40% major regional hub ports with LNG bunker barges or shore terminals",
        "vessel_compatibility": ["small_feeder", "handymax_feeder", "sub_panamax_feeder", "panamax_feeder"],
        "operational_constraints": [
            "Cryogenic containment (-162°C) with active boil-off gas (BOG) management",
            "Methane slip in low-pressure 4-stroke dual-fuel engines",
            "Specialized bunkering safety safety zone and IGF Code training",
        ],
        "co2e_factor": 3.720,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (IMO 4th GHG Study / DNV: 48.0 MJ/kg)",
            "prices": "Project Assumption (Henry Hub + liquefaction/bunker logistics: $720/t)",
            "emissions": "Real / Publicly Sourced (ICCT & IMO 4th GHG Study: 2.75 t TtW + 0.82 t WtT + 0.15 t Slip)",
            "storage": "Project Assumption (DNV Rules for Classification: 3% container slot displacement)",
            "availability": "Project Assumption (Regional Port Survey of Indian Ocean LNG Infrastructure)",
        },
    },
    "Methanol": {
        "fuel_key": "Methanol",
        "fuel_name": "Methanol (CH3OH)",
        "fuel_category": "Liquid Alternative Bio / E-Fuel",
        "energy_content_mj_kg": 19.9,
        "energy_density_label": "19.9 MJ/kg (LHV)",
        "engine_efficiency_ratio": 1.02,
        "price_usd_per_tonne": {"green": 980.0, "blue": 750.0, "grey": 480.0, "default": 980.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 5.0,
            "storage_type": "Liquid atmospheric coated tanks (ambient temperature)",
            "temperature_c": 20.0,
            "pressure_bar": 1.0,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 1.375,
            "ef_well_to_tank": {"green": 0.15, "blue": 0.85, "grey": 2.10, "default": 0.15},
            "slip_factor_co2e_per_tonne": 0.0,
            "total_wtw_co2e_per_tonne": {"green": 1.525, "blue": 2.225, "grey": 3.475, "default": 1.525},
        },
        "availability_assumption": "Growing: Bunkering hubs expanding at major transshipment ports (Singapore, Nhava Sheva)",
        "vessel_compatibility": ["small_feeder", "handymax_feeder", "sub_panamax_feeder", "panamax_feeder"],
        "operational_constraints": [
            "Low flashpoint (12°C, SOLAS low-flashpoint IGF Code applies)",
            "Requires ~2x bunkering tank mass/volume due to lower LHV (19.9 MJ/kg)",
            "Toxicity and specialized vapor detection systems",
        ],
        "co2e_factor": 1.525,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (IMO MEPC.1/Circ.877 / IEA: 19.9 MJ/kg)",
            "prices": "Project Assumption (IRENA Renewable Methanol 2025-2030: Green $980/t, Blue $750/t, Grey $480/t)",
            "emissions": "Real / Publicly Sourced (GREET Model & IMO LCA Guidelines: Green 1.525 t WtW, Grey 3.475 t WtW)",
            "storage": "Project Assumption (DNV Alternative Fuels Insight: 5% slot loss for double tank volume)",
            "availability": "Project Assumption (Maritime Methanol Bunkering Pipeline Survey)",
        },
    },
    "Ammonia": {
        "fuel_key": "Ammonia",
        "fuel_name": "Ammonia (NH3)",
        "fuel_category": "Zero-Carbon Molecule / E-Fuel",
        "energy_content_mj_kg": 18.6,
        "energy_density_label": "18.6 MJ/kg (LHV)",
        "engine_efficiency_ratio": 0.98,
        "price_usd_per_tonne": {"green": 1100.0, "blue": 790.0, "grey": 520.0, "default": 1100.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 9.0,
            "storage_type": "Refrigerated semi-pressurized Type-C tanks (-33°C)",
            "temperature_c": -33.0,
            "pressure_bar": 4.5,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 0.0,
            "ef_well_to_tank": {"green": 0.10, "blue": 0.95, "grey": 2.60, "default": 0.10},
            "slip_factor_co2e_per_tonne": 0.18,
            "total_wtw_co2e_per_tonne": {"green": 0.280, "blue": 1.130, "grey": 2.780, "default": 0.280},
        },
        "availability_assumption": "Emerging / Pilot: Chemical port berths and designated green shipping corridors",
        "vessel_compatibility": ["handymax_feeder", "sub_panamax_feeder", "panamax_feeder"],
        "operational_constraints": [
            "Severe toxicity and corrosive properties requiring strict crew safety zones",
            "SCR catalytic aftertreatment required for NOx and N2O slip abatement",
            "Not compatible with small feeders lacking heavy SCR/containment infrastructure",
        ],
        "co2e_factor": 0.280,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (IMO / Ammonia Energy Association: 18.6 MJ/kg)",
            "prices": "Project Assumption (Hydrogen Council / IRENA Future Fuel Outlook: Green $1,100/t, Blue $790/t, Grey $520/t)",
            "emissions": "Real / Publicly Sourced (IMO LCA Correspondence Group: Zero TtW, N2O slip penalty 0.18 t CO2e/t)",
            "storage": "Project Assumption (Class Society Studies: 9% slot loss for refrigerated tanks & safety buffer)",
            "availability": "Project Assumption (Regional Chemical Port Terminal Bunkering Feasibility)",
        },
    },
    "Hydrogen": {
        "fuel_key": "Hydrogen",
        "fuel_name": "Liquid Hydrogen (LH2)",
        "fuel_category": "Deep Cryogenic Zero-Carbon Fuel",
        "energy_content_mj_kg": 120.0,
        "energy_density_label": "120.0 MJ/kg (LHV)",
        "engine_efficiency_ratio": 1.15,
        "price_usd_per_tonne": {"green": 6500.0, "blue": 4800.0, "grey": 3200.0, "default": 6500.0},
        "tank_storage_factor": {
            "capacity_penalty_pct": 14.0,
            "storage_type": "Deep cryogenic vacuum-jacketed tanks (-253°C)",
            "temperature_c": -253.0,
            "pressure_bar": 3.0,
        },
        "lifecycle_emissions": {
            "ef_tank_to_wake": 0.0,
            "ef_well_to_tank": {"green": 0.50, "blue": 3.20, "grey": 11.50, "default": 0.50},
            "slip_factor_co2e_per_tonne": 0.0,
            "total_wtw_co2e_per_tonne": {"green": 0.50, "blue": 3.20, "grey": 11.50, "default": 0.50},
        },
        "availability_assumption": "Experimental: Dedicated pilot bunkering facilities for demonstration projects",
        "vessel_compatibility": ["small_feeder"],
        "operational_constraints": [
            "Extreme cryogenic temperature (-253°C) and boil-off gas rate",
            "Broad flammability range (4-75%) and hydrogen embrittlement of standard steels",
            "Very low volumetric density (large insulation space penalty, 14% slot loss)",
            "Suitable for short-sea coastal feeder fuel cells, unfeasible for large trunk routes",
        ],
        "co2e_factor": 0.50,
        "assumptions": {
            "energy_content": "Real / Publicly Sourced (US DOE / ISO 14687: 120.0 MJ/kg)",
            "prices": "Project Assumption (Clean Hydrogen Partnership / IEA 2025-2030: Green $6,500/t, Blue $4,800/t, Grey $3,200/t)",
            "emissions": "Real / Publicly Sourced (EU RED II / JRC Well-to-Wheels: Green 0.50 t WtW, Grey 11.50 t WtW)",
            "storage": "Project Assumption (Ship Design Hydrodynamics: 14% slot penalty from vacuum insulation)",
            "availability": "Synthetic / Illustrative (Prototype near-shore demo corridor)",
        },
    },
}


def build_candidate_options(
    allowed_fuels: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
    pathway_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """
    Dynamically generates valid candidate optimization options (vessel_type, fuel, pathway)
    enforcing strict vessel-fuel engineering compatibility and user fuel constraints.

    Args:
        allowed_fuels: List of permitted fuels (e.g. ['HFO', 'Methanol'] or ['LNG']).
        config: System configuration dictionary.
        pathway_map: Mapping of fuel -> pathway ('green', 'blue', 'grey', 'fossil').

    Returns:
        List of candidate option dicts, e.g. [{'vessel': 'handymax_feeder', 'fuel': 'LNG', 'pathway': 'fossil'}]
    """
    cfg = config or load_config()
    vessel_types = list(cfg["vessel_types"].keys())
    all_fuel_keys = list(cfg["fuels"].keys())

    fuels_to_include = [f for f in allowed_fuels if f in all_fuel_keys] if allowed_fuels else all_fuel_keys

    # Fallback to HFO if empty
    if not fuels_to_include:
        fuels_to_include = ["HFO"]

    pathways = pathway_map or {
        "HFO": "fossil",
        "MGO": "fossil",
        "LNG": "fossil",
        "Methanol": "green",
        "Ammonia": "green",
        "Hydrogen": "green",
    }

    candidates = []
    for v_type in vessel_types:
        compat_fuels = VESSEL_FUEL_COMPATIBILITY.get(v_type, ["HFO", "MGO"])
        for fuel in fuels_to_include:
            if fuel in compat_fuels:
                pathway = pathways.get(fuel, cfg["fuels"][fuel].get("default_pathway", "default"))
                candidates.append({
                    "vessel": v_type,
                    "fuel": fuel,
                    "pathway": pathway,
                })

    # If no compatible candidates were found (e.g. small_feeder + Ammonia only), fallback to compatible vessels
    if not candidates:
        for v_type in vessel_types:
            compat_fuels = VESSEL_FUEL_COMPATIBILITY.get(v_type, ["HFO"])
            for fuel in fuels_to_include:
                if fuel in compat_fuels:
                    candidates.append({"vessel": v_type, "fuel": fuel, "pathway": pathways.get(fuel, "default")})

    return candidates


def compare_fuels_for_voyage(
    vessel_key: str = "handymax_feeder",
    route_key: str = "R1",
    speed_knots: float = 14.5,
    cargo_load_tonnes: float = 16000.0,
    pathway_choices: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Compare all candidate fuels for a standard single voyage leg with detailed
    techno-economic, environmental, operational, and compatibility metrics.

    Returns DataFrame with columns:
    Fuel | Fuel Cost | Fuel Consumption | Lifecycle CO2e | Availability | Compatibility
    plus detailed engineering breakdown.
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
        "HFO": "fossil",
        "MGO": "fossil",
        "LNG": "fossil",
        "Methanol": "green",
        "Ammonia": "green",
        "Hydrogen": "green",
    }

    fuel_keys = ["HFO", "MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
    rows = []

    for fuel in fuel_keys:
        if fuel not in cfg["fuels"]:
            continue

        f_cfg = cfg["fuels"][fuel]
        meta = FUEL_STRUCTURED_PARAMETERS.get(fuel, {})
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

        # Vessel compatibility
        is_compatible = fuel in VESSEL_FUEL_COMPATIBILITY.get(vessel_key, [])
        compat_str = "Compatible" if is_compatible else "Incompatible (Engine/Hazmat Limit)"

        # Availability text summary
        avail_str = "High (Available at Hub)" if bunkering_feasible else "Limited (No Port Bunkering)"

        rows.append(
            {
                # Exact requested comparison columns
                "Fuel": meta.get("fuel_name", f_cfg.get("name", fuel)),
                "Fuel Cost": f"${int(round(fuel_cost)):,}",
                "Fuel Consumption": f"{round(mass_tonnes, 1)} t ({round(energy_gj, 0):,.0f} GJ)",
                "Lifecycle CO2e": f"{round(emiss['total_co2e'], 1)} t CO2e",
                "Availability": avail_str,
                "Compatibility": compat_str,
                # Technical raw attributes for plotting & state
                "fuel_type": fuel,
                "display_name": meta.get("fuel_name", f_cfg.get("name", fuel)),
                "category": meta.get("fuel_category", "Marine Fuel"),
                "pathway": pathway,
                "lhv_mj_kg": float(f_cfg["lhv_mj_kg"]),
                "fuel_mass_tonnes": round(mass_tonnes, 2),
                "energy_gj": round(energy_gj, 1),
                "fuel_price_usd_tonne": round(price_per_t, 1),
                "fuel_cost_usd": round(fuel_cost, 0),
                "ttw_co2e_tonnes": round(emiss["tank_to_wake"], 2),
                "wtt_co2e_tonnes": round(emiss["well_to_tank"], 2),
                "slip_co2e_tonnes": round(emiss.get("slip", 0.0), 2),
                "lifecycle_co2e_tonnes": round(emiss["total_co2e"], 2),
                "ghg_intensity_gco2e_mj": round(
                    (emiss["total_co2e"] * 1e6) / max(1.0, energy_gj * 1000.0), 1
                ),
                "cargo_loss_pct": penalty_pct,
                "usable_teu": round(usable_teu, 0),
                "bunkering_feasible": bunkering_feasible,
                "is_compatible": is_compatible,
                "availability_assumption": meta.get("availability_assumption", "N/A"),
                "operational_constraints": meta.get("operational_constraints", []),
                "assumption_labels": meta.get("assumptions", {}),
                "emission_profile": emiss.get("profile", {}),
                "emission_source": emiss.get("source", "Project assumption"),
                "emission_source_year": emiss.get("source_year", 2023),
                "emission_assumption_flag": emiss.get("assumption_flag", "Illustrative project assumptions"),
            }
        )

    return pd.DataFrame(rows)
