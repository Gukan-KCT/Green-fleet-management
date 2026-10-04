"""
Mathematical physics and economic models for the Green Fleet Management Platform.

Formulas implemented:
1. Fuel per sea leg:
   F_leg = F_daily * LoadFactor * WeatherFactor * LegTimeDays
   where:
     - F_daily = F_ref * (V / V_ref)^3
     - LoadFactor = ((Lightship + L) / (Lightship + L_ref))^(2/3)
     - WeatherFactor = 1 + k_w * WeatherSeverity
     - LegTimeDays = Distance / (24 * V)

2. Alternative fuel conversion (Energy Equivalence):
   mass_alt = mass_conv * (LHV_conv / LHV_alt) / (engine_efficiency_ratio_alt)

3. Emissions (Well-to-Wake CO2e):
   Emissions_total = fuel_mass * (EF_TtW + EF_WtT) + (fuel_mass * SlipFactor)

4. Operating Cost:
   Cost = FuelCost + FixedCost + PortCallCost + ShorePowerElectricityCost + CarbonPrice * Emissions

5. Usable Cargo Capacity Penalty:
   Capacity_usable = NominalCapacity * (1 - capacity_penalty_pct / 100)

6. Schedule Reliability:
   Reliability = max(0.0, min(1.0, 1.0 - 0.40 * (V / V_max)^2 - 0.35 * WeatherSeverity))
"""

from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml


@dataclass
class FuelEmissionProfile:
    """
    Structured lifecycle greenhouse gas (GHG) emission profile for maritime fuels.
    
    All emission factors are expressed in tonnes of CO2-equivalent per tonne of fuel (t CO2e / t fuel).
    
    Emissions accounting follows the Well-to-Wake (WtW) lifecycle framework:
      Lifecycle GHG = Well-to-Tank (WtT) + Tank-to-Wake (TtW) + Fuel/Methane Slip
    """
    fuel: str
    fuel_name: str
    pathway: str
    wtt_factor: float          # Well-to-Tank (upstream extraction, processing, transport) [t CO2e/t]
    ttw_factor: float          # Tank-to-Wake (onboard combustion / tailpipe emissions) [t CO2e/t]
    slip_factor: float         # Unburned hydrocarbon / methane slip or N2O penalty [t CO2e/t]
    lifecycle_factor: float    # Total Well-to-Wake factor (wtt + ttw + slip) [t CO2e/t]
    source: str                # Scientific / regulatory literature source
    source_year: int           # Year of source publication
    assumption_flag: str       # "Real / Publicly Sourced", "Project Assumption", or "Illustrative project assumptions"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary."""
        return asdict(self)


# Documented Provenance Catalog for Supported Fuels
FUEL_EMISSION_PROFILES_CATALOG: Dict[str, Dict[str, Dict[str, Any]]] = {
    "HFO": {
        "fossil": {
            "fuel": "HFO",
            "fuel_name": "Heavy Fuel Oil (HFO)",
            "pathway": "fossil",
            "wtt_factor": 0.58,
            "ttw_factor": 3.114,
            "slip_factor": 0.0,
            "lifecycle_factor": 3.694,
            "source": "IMO MEPC.308(73) & MEPC 80 LCA Guidelines / ISO 8217",
            "source_year": 2023,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Standard maritime residual fuel baseline with refinery upstream and marine diesel engine combustion.",
        }
    },
    "MGO": {
        "fossil": {
            "fuel": "MGO",
            "fuel_name": "Marine Gas Oil (MGO)",
            "pathway": "fossil",
            "wtt_factor": 0.65,
            "ttw_factor": 3.206,
            "slip_factor": 0.0,
            "lifecycle_factor": 3.856,
            "source": "IMO MEPC.308(73) & MEPC 80 LCA Guidelines",
            "source_year": 2023,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Low-sulfur distillate bunker fuel with universal global bunkering availability.",
        }
    },
    "LNG": {
        "fossil": {
            "fuel": "LNG",
            "fuel_name": "Liquefied Natural Gas (LNG)",
            "pathway": "fossil",
            "wtt_factor": 0.82,
            "ttw_factor": 2.750,
            "slip_factor": 0.15,
            "lifecycle_factor": 3.720,
            "source": "ICCT Marine LNG Life-Cycle Analysis & IMO 4th GHG Study",
            "source_year": 2020,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Includes 0.15 t CO2e/t methane slip (CH4 GWP-100 proxy) representing 4-stroke low-pressure dual-fuel auxiliary/propulsion engines.",
        }
    },
    "Methanol": {
        "green": {
            "fuel": "Methanol",
            "fuel_name": "Methanol (CH3OH)",
            "pathway": "green",
            "wtt_factor": 0.15,
            "ttw_factor": 1.375,
            "slip_factor": 0.0,
            "lifecycle_factor": 1.525,
            "source": "GREET Model & IMO MEPC.1/Circ.877 (Biogenic/Renewable E-Methanol)",
            "source_year": 2023,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Renewable e-methanol produced from green hydrogen and biogenic CO2. TtW reflects carbon in CH3OH molecule.",
        },
        "blue": {
            "fuel": "Methanol",
            "fuel_name": "Methanol (CH3OH)",
            "pathway": "blue",
            "wtt_factor": 0.85,
            "ttw_factor": 1.375,
            "slip_factor": 0.0,
            "lifecycle_factor": 2.225,
            "source": "IEA Maritime Fuel Report & DNV Alternative Fuels Insight",
            "source_year": 2023,
            "assumption_flag": "Project Assumption",
            "notes": "Natural gas steam reforming with 90% Carbon Capture & Storage (CCS).",
        },
        "grey": {
            "fuel": "Methanol",
            "fuel_name": "Methanol (CH3OH)",
            "pathway": "grey",
            "wtt_factor": 2.10,
            "ttw_factor": 1.375,
            "slip_factor": 0.0,
            "lifecycle_factor": 3.475,
            "source": "GREET / IMO LCA Correspondence Group",
            "source_year": 2022,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Unabated fossil natural gas reforming without carbon capture.",
        },
    },
    "Ammonia": {
        "green": {
            "fuel": "Ammonia",
            "fuel_name": "Ammonia (NH3)",
            "pathway": "green",
            "wtt_factor": 0.10,
            "ttw_factor": 0.0,
            "slip_factor": 0.18,
            "lifecycle_factor": 0.280,
            "source": "IMO LCA Correspondence Group & Ammonia Energy Association",
            "source_year": 2023,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Electrolytic green hydrogen Haber-Bosch. Zero tailpipe carbon; includes 0.18 t CO2e/t N2O combustion slip penalty.",
        },
        "blue": {
            "fuel": "Ammonia",
            "fuel_name": "Ammonia (NH3)",
            "pathway": "blue",
            "wtt_factor": 0.95,
            "ttw_factor": 0.0,
            "slip_factor": 0.18,
            "lifecycle_factor": 1.130,
            "source": "Hydrogen Council / IRENA Future Fuel Outlook",
            "source_year": 2023,
            "assumption_flag": "Project Assumption",
            "notes": "Fossil methane reforming with CCS Haber-Bosch synthesis.",
        },
        "grey": {
            "fuel": "Ammonia",
            "fuel_name": "Ammonia (NH3)",
            "pathway": "grey",
            "wtt_factor": 2.60,
            "ttw_factor": 0.0,
            "slip_factor": 0.18,
            "lifecycle_factor": 2.780,
            "source": "GREET / IEA Ammonia Technology Roadmap",
            "source_year": 2022,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Conventional unabated Haber-Bosch from natural gas or coal.",
        },
    },
    "Hydrogen": {
        "green": {
            "fuel": "Hydrogen",
            "fuel_name": "Liquid Hydrogen (LH2)",
            "pathway": "green",
            "wtt_factor": 0.50,
            "ttw_factor": 0.0,
            "slip_factor": 0.0,
            "lifecycle_factor": 0.50,
            "source": "EU RED II / JRC Well-to-Wheels & ISO 14687",
            "source_year": 2023,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Electrolysis from renewable power plus cryogenic liquefaction (-253°C). Zero tailpipe emissions.",
        },
        "blue": {
            "fuel": "Hydrogen",
            "fuel_name": "Liquid Hydrogen (LH2)",
            "pathway": "blue",
            "wtt_factor": 3.20,
            "ttw_factor": 0.0,
            "slip_factor": 0.0,
            "lifecycle_factor": 3.20,
            "source": "Clean Hydrogen Partnership / IEA 2023",
            "source_year": 2023,
            "assumption_flag": "Project Assumption",
            "notes": "Steam Methane Reforming (SMR) with CCS + cryogenic liquefaction.",
        },
        "grey": {
            "fuel": "Hydrogen",
            "fuel_name": "Liquid Hydrogen (LH2)",
            "pathway": "grey",
            "wtt_factor": 11.50,
            "ttw_factor": 0.0,
            "slip_factor": 0.0,
            "lifecycle_factor": 11.50,
            "source": "EU JRC / US DOE Hydrogen Life Cycle Analysis",
            "source_year": 2022,
            "assumption_flag": "Real / Publicly Sourced",
            "notes": "Unabated SMR of fossil gas + liquefaction energy penalty.",
        },
    },
}


def get_fuel_emission_profile(
    fuel_type: str,
    pathway: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> FuelEmissionProfile:
    """
    Retrieve structured FuelEmissionProfile for any supported marine fuel and production pathway.
    
    If the fuel/pathway is present in FUEL_EMISSION_PROFILES_CATALOG, it returns the verified scientific
    or project assumption record. If not documented, it falls back to config parameters labeled as
    'Illustrative project assumptions'.
    """
    cfg = config or load_config()
    fuel_key = fuel_type.strip() if isinstance(fuel_type, str) else "HFO"
    if fuel_key not in cfg.get("fuels", {}):
        fuel_key = "HFO"

    fuel_cfg = cfg["fuels"][fuel_key]
    default_pw = fuel_cfg.get("default_pathway", "default")
    pw = pathway or default_pw

    # Normalize pathway
    if pw == "default":
        pw = default_pw

    # Check verified catalog first
    if fuel_key in FUEL_EMISSION_PROFILES_CATALOG:
        pw_dict = FUEL_EMISSION_PROFILES_CATALOG[fuel_key]
        if pw in pw_dict:
            rec = pw_dict[pw]
            return FuelEmissionProfile(
                fuel=rec["fuel"],
                fuel_name=rec["fuel_name"],
                pathway=rec["pathway"],
                wtt_factor=float(rec["wtt_factor"]),
                ttw_factor=float(rec["ttw_factor"]),
                slip_factor=float(rec["slip_factor"]),
                lifecycle_factor=float(rec["lifecycle_factor"]),
                source=rec["source"],
                source_year=rec["source_year"],
                assumption_flag=rec["assumption_flag"],
                notes=rec.get("notes", ""),
            )
        elif "fossil" in pw_dict:
            rec = pw_dict["fossil"]
            return FuelEmissionProfile(
                fuel=rec["fuel"],
                fuel_name=rec["fuel_name"],
                pathway=rec["pathway"],
                wtt_factor=float(rec["wtt_factor"]),
                ttw_factor=float(rec["ttw_factor"]),
                slip_factor=float(rec["slip_factor"]),
                lifecycle_factor=float(rec["lifecycle_factor"]),
                source=rec["source"],
                source_year=rec["source_year"],
                assumption_flag=rec["assumption_flag"],
                notes=rec.get("notes", ""),
            )

    # Fallback to config values and label as Illustrative project assumptions
    ef_ttw = float(fuel_cfg.get("ef_tank_to_wake", 0.0))
    wt_t_spec = fuel_cfg.get("ef_well_to_tank", {})
    if isinstance(wt_t_spec, dict):
        ef_wtt = float(wt_t_spec.get(pw, wt_t_spec.get("default", 0.58)))
    else:
        ef_wtt = float(wt_t_spec)

    slip = float(fuel_cfg.get("slip_factor_co2e_per_tonne", 0.0))
    total = ef_ttw + ef_wtt + slip

    return FuelEmissionProfile(
        fuel=fuel_key,
        fuel_name=fuel_cfg.get("name", fuel_key),
        pathway=pw,
        wtt_factor=ef_wtt,
        ttw_factor=ef_ttw,
        slip_factor=slip,
        lifecycle_factor=total,
        source="System Configuration (config/params.yaml)",
        source_year=2024,
        assumption_flag="Illustrative project assumptions",
        notes="Configured fallback parameter set without external source confirmation.",
    )


def list_all_emission_profiles(config: Optional[Dict[str, Any]] = None) -> List[FuelEmissionProfile]:
    """Return all configured and supported FuelEmissionProfiles across fuels and pathways."""
    cfg = config or load_config()
    profiles: List[FuelEmissionProfile] = []
    for f_key in cfg.get("fuels", {}):
        f_info = cfg["fuels"][f_key]
        pathways = f_info.get("pathways", [f_info.get("default_pathway", "default")])
        for pw in pathways:
            profiles.append(get_fuel_emission_profile(f_key, pw, cfg))
    return profiles


def load_config(config_path: str | Path = "config/params.yaml") -> Dict[str, Any]:
    """Load system configuration containing illustrative parameters."""
    path = Path(config_path)
    if not path.is_file():
        # Fallback to look up from workspace root if running from child directory
        candidate = Path(__file__).resolve().parents[2] / config_path
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def calculate_leg_fuel_conventional(
    vessel_cfg: Dict[str, Any],
    speed_knots: float,
    distance_nm: float,
    cargo_load_tonnes: float,
    weather_severity: float,
    k_w: float = 0.35,
) -> Tuple[float, float]:
    """
    Calculate conventional fuel (HFO baseline) consumed on a single leg in tonnes,
    along with leg duration in days.

    Args:
        vessel_cfg: Vessel specifications dictionary from config.
        speed_knots: Cruising speed V in knots.
        distance_nm: One-way nautical distance d.
        cargo_load_tonnes: Actual cargo load L in tonnes.
        weather_severity: Severity index in [0, 1].
        k_w: Weather penalty coefficient.

    Returns:
        (leg_fuel_tonnes_hfo, leg_time_days)
    """
    v_ref = float(vessel_cfg["v_ref_knots"])
    f_ref = float(vessel_cfg["f_ref_tonnes_day"])
    lightship = float(vessel_cfg["lightship_tonnes"])
    l_ref = float(vessel_cfg["l_ref_tonnes"])

    # Enforce safe speed boundary
    speed = max(0.1, float(speed_knots))
    distance = max(0.0, float(distance_nm))
    cargo = max(0.0, float(cargo_load_tonnes))
    weather = max(0.0, min(1.0, float(weather_severity)))

    # 1. Speed effect: cubic law of propulsion power
    speed_ratio = speed / v_ref
    daily_fuel = f_ref * (speed_ratio**3)

    # 2. Load effect: displacement scaling (Admiralty coefficient law, 2/3 power)
    total_disp = lightship + cargo
    ref_disp = lightship + l_ref
    load_factor = (total_disp / ref_disp) ** (2.0 / 3.0)

    # 3. Weather effect
    weather_factor = 1.0 + (k_w * weather)

    # 4. Leg transit duration
    leg_time_days = distance / (24.0 * speed)

    # 5. Total fuel on leg (tonnes of conventional HFO)
    leg_fuel = daily_fuel * load_factor * weather_factor * leg_time_days

    return leg_fuel, leg_time_days


def calculate_alternative_fuel_mass(
    conv_fuel_mass_tonnes: float,
    fuel_type: str,
    config: Dict[str, Any],
) -> float:
    """
    Convert conventional fuel consumption (HFO baseline) into alternative fuel mass
    using the principle of energy equivalence:
      mass_alt = mass_conv * (LHV_conv / LHV_alt) / (engine_efficiency_ratio_alt)
    """
    fuels_cfg = config["fuels"]
    conv_cfg = fuels_cfg["HFO"]
    lhv_conv = float(conv_cfg["lhv_mj_kg"])

    if fuel_type not in fuels_cfg:
        raise ValueError(f"Unknown fuel type: '{fuel_type}'. Supported: {list(fuels_cfg.keys())}")

    target_cfg = fuels_cfg[fuel_type]
    lhv_alt = float(target_cfg["lhv_mj_kg"])
    eff_ratio = float(target_cfg.get("engine_efficiency_ratio", 1.0))

    if lhv_alt <= 0:
        raise ValueError(f"LHV for {fuel_type} must be positive.")

    mass_alt = conv_fuel_mass_tonnes * (lhv_conv / lhv_alt) / eff_ratio
    return mass_alt


def calculate_fuel_energy_gj(fuel_mass_tonnes: float, fuel_type: str, config: Dict[str, Any]) -> float:
    """
    Calculate total energy content in Gigajoules (GJ).
    1 tonne = 1,000 kg. LHV is in MJ/kg.
    Energy (GJ) = tonnes * 1,000 kg/t * (LHV MJ/kg) / 1,000 MJ/GJ = tonnes * LHV.
    """
    fuels_cfg = config["fuels"]
    lhv_mj_kg = float(fuels_cfg[fuel_type]["lhv_mj_kg"])
    return fuel_mass_tonnes * lhv_mj_kg


def calculate_emissions(
    fuel_mass_tonnes: float,
    fuel_type: str,
    pathway: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate lifecycle GHG emissions (tonnes CO2e) separated into:
    - Tank-to-Wake (combustion/tailpipe emissions)
    - Well-to-Tank (upstream extraction, production, transport)
    - Methane / Fuel Slip (unburned slip e.g. for LNG and N2O for Ammonia)
    - Total Well-to-Wake (WtT + TtW + Slip)

    Returns dictionary with exact breakdown and attached FuelEmissionProfile metadata.
    """
    if config is None:
        config = load_config()

    profile = get_fuel_emission_profile(fuel_type, pathway, config)

    ttw_emissions = fuel_mass_tonnes * profile.ttw_factor
    wtt_emissions = fuel_mass_tonnes * profile.wtt_factor
    slip_emissions = fuel_mass_tonnes * profile.slip_factor
    total_co2e = ttw_emissions + wtt_emissions + slip_emissions

    return {
        "tank_to_wake": ttw_emissions,
        "well_to_tank": wtt_emissions,
        "slip": slip_emissions,
        "total_co2e": total_co2e,
        "pathway_used": profile.pathway,
        "fuel": profile.fuel,
        "fuel_name": profile.fuel_name,
        "wtt_factor": profile.wtt_factor,
        "ttw_factor": profile.ttw_factor,
        "slip_factor": profile.slip_factor,
        "lifecycle_factor": profile.lifecycle_factor,
        "source": profile.source,
        "source_year": profile.source_year,
        "assumption_flag": profile.assumption_flag,
        "notes": profile.notes,
        "profile": profile.to_dict(),
    }


def get_fuel_price_usd_per_tonne(
    fuel_type: str,
    pathway: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Get illustrative fuel price per tonne depending on production pathway."""
    if config is None:
        config = load_config()

    fuel_cfg = config["fuels"][fuel_type]
    price_spec = fuel_cfg["price_usd_per_tonne"]
    if isinstance(price_spec, dict):
        selected_pathway = pathway or fuel_cfg.get("default_pathway", "default")
        return float(price_spec.get(selected_pathway, price_spec.get("default", 600.0)))
    return float(price_spec)


def calculate_usable_capacity_teu(
    nominal_teu: float,
    fuel_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Calculate net usable TEU capacity after accounting for alternative fuel tank volumetric penalty.
    """
    if config is None:
        config = load_config()

    fuel_cfg = config["fuels"][fuel_type]
    penalty_pct = float(fuel_cfg.get("capacity_penalty_pct", 0.0))
    usable_factor = max(0.0, 1.0 - (penalty_pct / 100.0))
    return nominal_teu * usable_factor


def calculate_schedule_reliability(
    speed_knots: float,
    v_max_knots: float,
    weather_severity: float,
) -> float:
    """
    Compute operational schedule reliability index in [0, 1].
    Reliability drops non-linearly as cruising speed approaches engine limit (no margin for delay recovery)
    and drops linearly with rough weather severity.
    """
    v_ratio = max(0.0, min(1.0, speed_knots / max(1.0, v_max_knots)))
    weather = max(0.0, min(1.0, weather_severity))

    # Quadratic penalty for speed saturation, linear penalty for adverse seas
    reliability = 1.0 - 0.25 * (v_ratio**2) - 0.20 * weather
    return max(0.0, min(1.0, reliability))


def calculate_berth_energy_and_emissions(
    aux_kw: float,
    berth_hours: float,
    use_shore_power: bool,
    port_cfg: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Calculate port berth auxiliary energy consumption, cost, and emissions.
    If shore power is used and available:
      Uses port electric grid (kWh), with local grid emission factor and electricity tariff.
    Without shore power (or if unavailable):
      Runs onboard auxiliary generator burning MGO.
      Auxiliary engine specific fuel consumption (SFOC) ~ 210 g MGO / kWh = 0.000210 t / kWh.
    """
    if config is None:
        config = load_config()

    kwh_required = aux_kw * berth_hours
    mwh_required = kwh_required / 1000.0

    port_has_sp = bool(port_cfg.get("has_shore_power", False))

    if use_shore_power and port_has_sp:
        # Powered by shore grid
        grid_ef = float(port_cfg.get("grid_ef_tonnes_per_mwh", 0.65))
        elec_tariff = float(port_cfg.get("electricity_price_usd_per_mwh", 120.0))

        cost_usd = mwh_required * elec_tariff
        emissions_co2e = mwh_required * grid_ef
        fuel_tonnes = 0.0
        power_source = "shore_grid"
    else:
        # Powered by onboard auxiliary generator using MGO
        sfoc_tonnes_per_kwh = 0.000210  # 210 g/kWh typical 4-stroke auxiliary gen
        fuel_tonnes = kwh_required * sfoc_tonnes_per_kwh

        mgo_price = get_fuel_price_usd_per_tonne("MGO", config=config)
        cost_usd = fuel_tonnes * mgo_price

        mgo_emissions = calculate_emissions(fuel_tonnes, "MGO", config=config)
        emissions_co2e = mgo_emissions["total_co2e"]
        power_source = "onboard_aux_gen"

    return {
        "kwh_required": kwh_required,
        "mwh_required": mwh_required,
        "fuel_tonnes": fuel_tonnes,
        "cost_usd": cost_usd,
        "emissions_co2e": emissions_co2e,
        "power_source": power_source,
    }
