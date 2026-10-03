"""
Scenario Analysis Module.

Evaluates fleet deployment sensitivity across economic, operational, and regulatory stresses:
- Presets: Baseline, High Fuel Price (+50%), Demand Surge (+25%), Strict Emission Cap,
  Rough Weather Season, Slow Steaming Mandate.
- Custom user-defined scenario parameters.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import pandas as pd

from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.models.physics import load_config


PRESET_SCENARIOS = {
    "Baseline Policy": {
        "description": "Standard business-as-usual operating conditions with nominal parameters.",
        "fuel_price_multiplier": 1.0,
        "demand_multiplier": 1.0,
        "weather_multiplier": 1.0,
        "speed_cap_delta": 0.0,
        "carbon_intensity_cap": 18.0,
        "shore_power_forced": None,
    },
    "High Fuel Price (+50%)": {
        "description": "Global bunker price shock pushing alternative fuel competitiveness.",
        "fuel_price_multiplier": 1.50,
        "demand_multiplier": 1.0,
        "weather_multiplier": 1.0,
        "speed_cap_delta": 0.0,
        "carbon_intensity_cap": 18.0,
        "shore_power_forced": None,
    },
    "Demand Surge (+25%)": {
        "description": "Regional feeder cargo boom requiring maximum slot capacity utilization.",
        "fuel_price_multiplier": 1.0,
        "demand_multiplier": 1.25,
        "weather_multiplier": 1.0,
        "speed_cap_delta": 0.0,
        "carbon_intensity_cap": 20.0,
        "shore_power_forced": None,
    },
    "Strict Emission Cap": {
        "description": "Aggressive regional decarbonization regulation (tight carbon intensity proxy cap + mandatory cold ironing).",
        "fuel_price_multiplier": 1.0,
        "demand_multiplier": 1.0,
        "weather_multiplier": 1.0,
        "speed_cap_delta": 0.0,
        "carbon_intensity_cap": 13.0,
        "shore_power_forced": True,
    },
    "Rough Weather Season": {
        "description": "Monsoon/adverse sea states increasing hydrodynamic resistance and testing schedule reliability.",
        "fuel_price_multiplier": 1.0,
        "demand_multiplier": 1.0,
        "weather_multiplier": 1.35,
        "speed_cap_delta": -1.0,
        "carbon_intensity_cap": 18.0,
        "shore_power_forced": None,
    },
    "Slow Steaming Mandate": {
        "description": "Port authority / environmental speed restriction lowering corridor speed ceilings.",
        "fuel_price_multiplier": 1.0,
        "demand_multiplier": 1.0,
        "weather_multiplier": 1.0,
        "speed_cap_delta": -3.0,
        "carbon_intensity_cap": 16.0,
        "shore_power_forced": None,
    },
}


def evaluate_scenario(
    scenario_name: str,
    params_override: Optional[Dict[str, Any]] = None,
    pop_size: int = 20,
    generations: int = 30,
    random_seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the QIEA optimizer under specific scenario parameters.
    """
    cfg = config or load_config()

    if scenario_name in PRESET_SCENARIOS:
        scenario_params = dict(PRESET_SCENARIOS[scenario_name])
    else:
        scenario_params = {
            "description": "Custom Scenario",
            "fuel_price_multiplier": 1.0,
            "demand_multiplier": 1.0,
            "weather_multiplier": 1.0,
            "speed_cap_delta": 0.0,
            "carbon_intensity_cap": 18.0,
            "shore_power_forced": None,
        }

    if params_override:
        scenario_params.update(params_override)

    prob = FleetOptimizationProblem(
        config=cfg,
        fuel_price_multiplier=scenario_params["fuel_price_multiplier"],
        demand_multiplier=scenario_params["demand_multiplier"],
        weather_multiplier=scenario_params["weather_multiplier"],
        speed_cap_delta=scenario_params["speed_cap_delta"],
        carbon_intensity_cap=scenario_params["carbon_intensity_cap"],
        shore_power_forced=scenario_params["shore_power_forced"],
    )

    optimizer = QIEA(
        n_bits=prob.n_bits,
        pop_size=pop_size,
        generations=generations,
        random_seed=random_seed,
        initial_theta=prob.get_initial_q_angles(),
    )

    opt_result = optimizer.optimize(prob.fitness_function)
    eval_result = prob.evaluate(opt_result["best_bits"])

    eval_result["scenario_name"] = scenario_name
    eval_result["scenario_params"] = scenario_params
    eval_result["convergence_curve"] = opt_result["convergence_curve"]
    eval_result["evaluations"] = opt_result["evaluations"]

    return eval_result


def run_all_preset_scenarios(
    pop_size: int = 15,
    generations: int = 25,
    random_seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """
    Execute all preset scenarios and return a comparison summary DataFrame and detail mappings.
    """
    cfg = config or load_config()
    summary_rows = []
    details_map = {}

    for name in PRESET_SCENARIOS.keys():
        res = evaluate_scenario(
            scenario_name=name,
            params_override=None,
            pop_size=pop_size,
            generations=generations,
            random_seed=random_seed,
            config=cfg,
        )
        details_map[name] = res

        summary_rows.append(
            {
                "Scenario": name,
                "Feasible": "Yes" if res["is_feasible"] else "No",
                "Total Fuel (t HFO-eq)": round(res["total_fuel_tonnes_hfo_eq"], 0),
                "Total Cost ($M)": round(res["total_operating_cost_usd"] / 1e6, 2),
                "GHG Emissions (kt CO2e)": round(res["total_emissions_co2e_tonnes"] / 1000.0, 2),
                "Carbon Intensity (g/t-nm)": round(res["carbon_intensity_g_tnm"], 2),
                "Total TEU Delivered": round(res["total_cargo_delivered_teu"], 0),
                "Total Vessels Deployed": sum(res["vessels_used_by_type"].values()),
                "Violations": round(res["total_violation_score"], 2),
            }
        )

    df_summary = pd.DataFrame(summary_rows)
    return df_summary, details_map
