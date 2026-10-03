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
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import yaml


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
) -> Dict[str, float]:
    """
    Calculate lifecycle GHG emissions (tonnes CO2e) separated into:
    - Tank-to-Wake (combustion/tailpipe)
    - Well-to-Tank (upstream extraction, production, transport)
    - Fuel Slip (e.g. unburned methane slip for LNG, N2O for ammonia)
    - Total Well-to-Wake (TtW + WtT + Slip)
    """
    if config is None:
        config = load_config()

    fuel_cfg = config["fuels"][fuel_type]

    # Tank-to-Wake emission factor
    ef_ttw = float(fuel_cfg.get("ef_tank_to_wake", 0.0))

    # Well-to-Tank emission factor by pathway
    wt_t_spec = fuel_cfg.get("ef_well_to_tank", {})
    if isinstance(wt_t_spec, dict):
        selected_pathway = pathway or fuel_cfg.get("default_pathway", "default")
        ef_wtt = float(wt_t_spec.get(selected_pathway, wt_t_spec.get("default", 0.0)))
    else:
        ef_wtt = float(wt_t_spec)

    # Slip factor
    slip_factor = float(fuel_cfg.get("slip_factor_co2e_per_tonne", 0.0))

    ttw_emissions = fuel_mass_tonnes * ef_ttw
    wtt_emissions = fuel_mass_tonnes * ef_wtt
    slip_emissions = fuel_mass_tonnes * slip_factor
    total_co2e = ttw_emissions + wtt_emissions + slip_emissions

    return {
        "tank_to_wake": ttw_emissions,
        "well_to_tank": wtt_emissions,
        "slip": slip_emissions,
        "total_co2e": total_co2e,
        "pathway_used": pathway or fuel_cfg.get("default_pathway", "default"),
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
