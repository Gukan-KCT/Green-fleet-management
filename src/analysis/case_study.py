"""
Regional Feeder Case Study and Operational Simulation Engine.

Simulates and compares:
1. Feasible Naive Baseline: Conventional HFO bunkering, fixed service speed, no shore power,
   adjusted until all operational constraints are satisfied (or reported explicitly if not).
2. Best Conventional Baseline: Optimizer restricted to conventional HFO options and no shore power.
3. Multi-Objective Optimized Green Fleet Plan: Optimizer searching all clean fuels (LNG, Methanol, Ammonia),
   variable eco-speeds, and shore power connections. Guaranteed not worse than the best conventional baseline.

Network: 5 Regional Feeder Corridors connecting Nhava Sheva (Mumbai), Kochi, Tuticorin, Chennai, Colombo, and Singapore.
"""

from __future__ import annotations
import copy
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS
from src.optimization.qiea import QIEA


def format_signed_change(diff: float, diff_pct: Optional[float] = None, unit: str = "") -> str:
    """
    Format numeric differences with explicit sign and directional words.
    Rule: Never describe an increase as an improvement or saving.
    """
    if abs(diff) < 1e-6:
        return f"0.0 {unit} (no change)".strip()
    sign = "+" if diff > 0 else "-"
    direction = "increase" if diff > 0 else "decrease"
    abs_diff = abs(diff)
    if diff_pct is not None:
        return f"{sign}{abs_diff:,.1f} {unit} ({sign}{abs(diff_pct):.1f}% {direction})".strip()
    return f"{sign}{abs_diff:,.1f} {unit} ({direction})".strip()


def get_naive_baseline(problem: FleetOptimizationProblem) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Construct a deterministic conventional HFO baseline with a fixed speed and no shore power.
    Systematically adjusts speed and allocations until ALL constraints are satisfied.
    If constraints cannot be satisfied, returns the best found configuration and explicitly
    flags is_feasible=False.
    """
    # HFO Candidate option indices in DEFAULT_CANDIDATE_OPTIONS:
    # 0: small_feeder (HFO)
    # 2: handymax_feeder (HFO)
    # 5: sub_panamax_feeder (HFO)
    # Search structured allocation candidates that assign sufficient HFO capacity to meet demand
    hfo_alloc_candidates = [
        # Candidate A: balanced Handymax + Small + Sub-Panamax
        {(2, 0): 2, (2, 1): 1, (2, 2): 1, (0, 2): 1, (0, 3): 1, (5, 4): 3},
        # Candidate B: Small feeder on short routes, Handymax on medium, Sub-Panamax on R5
        {(2, 0): 2, (0, 1): 2, (2, 2): 2, (0, 3): 1, (5, 4): 3},
        # Candidate C: Handymax on R1-R3, Small on R4, Sub-Panamax on R5
        {(2, 0): 2, (2, 1): 1, (2, 2): 2, (0, 3): 1, (5, 4): 3},
        # Candidate D: Generous fleet allocation
        {(2, 0): 3, (2, 1): 1, (2, 2): 2, (0, 3): 2, (5, 4): 3},
    ]

    best_bits = None
    best_eval = None
    best_violation = float("inf")

    # Evaluate across all fixed speed levels (0 to 7)
    for alloc_dict in hfo_alloc_candidates:
        for spd_idx in range(problem.speed_levels_count):
            bits = np.zeros(problem.n_bits, dtype=int)
            idx = 0
            for o in range(len(problem.options)):
                for r in range(len(problem.route_keys)):
                    val = alloc_dict.get((o, r), 0)
                    bits[idx] = (val >> 1) & 1
                    bits[idx + 1] = val & 1
                    idx += 2
            for r in range(len(problem.route_keys)):
                bits[idx] = (spd_idx >> 2) & 1
                bits[idx + 1] = (spd_idx >> 1) & 1
                bits[idx + 2] = spd_idx & 1
                idx += 3
            # Shore power: all 0 (no shore power used)
            for p in range(len(problem.port_keys)):
                bits[idx] = 0
                idx += 1

            ev = problem.evaluate(bits)
            if ev["is_feasible"]:
                return bits, ev

            if ev["total_violation_score"] < best_violation:
                best_violation = ev["total_violation_score"]
                best_bits = bits
                best_eval = ev

    return best_bits, best_eval


def get_best_conventional_baseline(
    problem: FleetOptimizationProblem,
    pop_size: int = 40,
    generations: int = 100,
    random_seed: int = 42,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Construct the 'Best Conventional' baseline by restricting the optimizer to
    conventional HFO options and disabling shore power.
    """
    hfo_options = [opt for opt in problem.options if opt["fuel"] == "HFO"]
    conv_problem = FleetOptimizationProblem(
        config=problem.config,
        candidate_options=hfo_options,
        routes_override=problem.routes,
        fuel_price_multiplier=problem.fuel_price_multiplier,
        demand_multiplier=problem.demand_multiplier,
        weather_multiplier=problem.weather_multiplier,
        speed_cap_delta=problem.speed_cap_delta,
        shore_power_forced=False,
        carbon_intensity_cap=problem.carbon_intensity_cap,
        supply_cap_ratio=problem.supply_cap_ratio,
    )

    optimizer = QIEA(
        n_bits=conv_problem.n_bits,
        pop_size=pop_size,
        generations=generations,
        random_seed=random_seed,
        initial_theta=conv_problem.get_initial_q_angles(),
    )
    res = optimizer.optimize(conv_problem.fitness_function)
    allocs, speeds, _ = conv_problem.decode_solution(res["best_bits"])

    # Map decoded conventional solution into the full problem's chromosome layout
    full_bits = np.zeros(problem.n_bits, dtype=int)
    idx = 0
    for o_idx, opt in enumerate(problem.options):
        for r_idx, r_k in enumerate(problem.route_keys):
            val = 0
            if opt in hfo_options:
                c_idx = hfo_options.index(opt)
                val = allocs[c_idx, r_idx]
            full_bits[idx] = (val >> 1) & 1
            full_bits[idx + 1] = val & 1
            idx += 2

    for r_k in problem.route_keys:
        spd_val = int(round((speeds[r_k] - 10.5) / 1.0))
        spd_val = max(0, min(7, spd_val))
        full_bits[idx] = (spd_val >> 2) & 1
        full_bits[idx + 1] = (spd_val >> 1) & 1
        full_bits[idx + 2] = spd_val & 1
        idx += 3

    for p_k in problem.port_keys:
        full_bits[idx] = 0
        idx += 1

    best_conv_eval = problem.evaluate(full_bits)
    return full_bits, best_conv_eval


def simulate_monthly_operations(
    problem: FleetOptimizationProblem,
    naive_bits: np.ndarray,
    best_conv_bits: np.ndarray,
    optimized_bits: np.ndarray,
) -> pd.DataFrame:
    """
    Perform a real monthly simulation across 12 calendar months with realistic
    monsoon weather severity multipliers for the Indian Ocean and Bay of Bengal.
    """
    month_data = [
        ("Jan", 31, 1.10),
        ("Feb", 28, 0.85),
        ("Mar", 31, 0.85),
        ("Apr", 30, 0.90),
        ("May", 31, 1.15),
        ("Jun", 30, 1.55),
        ("Jul", 31, 1.65),
        ("Aug", 31, 1.50),
        ("Sep", 30, 1.25),
        ("Oct", 31, 0.95),
        ("Nov", 30, 1.20),
        ("Dec", 31, 1.25),
    ]

    monthly_rows = []
    base_eval_naive = problem.evaluate(naive_bits)
    base_eval_conv = problem.evaluate(best_conv_bits)
    base_eval_opt = problem.evaluate(optimized_bits)

    for m_name, days, weather_mult in month_data:
        # Month proportion of operational year (350 days)
        m_frac = days / 365.0
        # Fuel consumption scales with weather severity multiplier
        fuel_naive = base_eval_naive["total_fuel_tonnes_hfo_eq"] * m_frac * (0.85 + 0.15 * weather_mult)
        fuel_conv = base_eval_conv["total_fuel_tonnes_hfo_eq"] * m_frac * (0.85 + 0.15 * weather_mult)
        fuel_opt = base_eval_opt["total_fuel_tonnes_hfo_eq"] * m_frac * (0.85 + 0.15 * weather_mult)

        # Cost scales with fuel plus time charter and port costs
        cost_naive = (base_eval_naive["total_operating_cost_usd"] * m_frac * (0.90 + 0.10 * weather_mult)) / 1e6
        cost_conv = (base_eval_conv["total_operating_cost_usd"] * m_frac * (0.90 + 0.10 * weather_mult)) / 1e6
        cost_opt = (base_eval_opt["total_operating_cost_usd"] * m_frac * (0.90 + 0.10 * weather_mult)) / 1e6

        emiss_naive = (base_eval_naive["total_emissions_co2e_tonnes"] * m_frac * (0.85 + 0.15 * weather_mult)) / 1000.0
        emiss_conv = (base_eval_conv["total_emissions_co2e_tonnes"] * m_frac * (0.85 + 0.15 * weather_mult)) / 1000.0
        emiss_opt = (base_eval_opt["total_emissions_co2e_tonnes"] * m_frac * (0.85 + 0.15 * weather_mult)) / 1000.0

        monthly_rows.append(
            {
                "Month": m_name,
                "Days": days,
                "Monsoon Multiplier": weather_mult,
                "Naive Fuel (t)": round(fuel_naive, 1),
                "Best Conv Fuel (t)": round(fuel_conv, 1),
                "Optimized Fuel (t)": round(fuel_opt, 1),
                "Naive Cost ($M)": round(cost_naive, 2),
                "Best Conv Cost ($M)": round(cost_conv, 2),
                "Optimized Cost ($M)": round(cost_opt, 2),
                "Naive CO2e (kt)": round(emiss_naive, 2),
                "Best Conv CO2e (kt)": round(emiss_conv, 2),
                "Optimized CO2e (kt)": round(emiss_opt, 2),
            }
        )

    return pd.DataFrame(monthly_rows)


def run_case_study(
    pop_size: int = 50,
    generations: int = 200,
    random_seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run complete comparative Case Study between:
    1. Feasible Naive Baseline (Conventional HFO, fixed speed, no shore power)
    2. Best Conventional Baseline (Optimizer restricted to HFO, no shore power)
    3. Multi-Objective Optimized Plan (Clean fuels, eco-speeds, shore power)
    """
    cfg = config or load_config()
    problem = FleetOptimizationProblem(config=cfg)

    # 1. Evaluate Naive Baseline
    naive_bits, naive_eval = get_naive_baseline(problem)

    # 2. Evaluate Best Conventional Baseline
    best_conv_bits, best_conv_eval = get_best_conventional_baseline(
        problem=problem,
        pop_size=min(40, pop_size),
        generations=min(100, generations),
        random_seed=random_seed,
    )

    # 3. Run QIEA Optimization seeded with best conventional baseline to ensure
    # that the optimized green plan is NEVER worse than the best conventional baseline
    optimizer = QIEA(
        n_bits=problem.n_bits,
        pop_size=pop_size,
        generations=generations,
        random_seed=random_seed,
        initial_theta=problem.get_initial_q_angles(),
    )
    opt_res = optimizer.optimize(problem.fitness_function, seed_bits=best_conv_bits)
    optimized_bits = opt_res["best_bits"]
    optimized_eval = problem.evaluate(optimized_bits)

    # 4. Compute Metrics & Comparative Deltas against both baselines
    def compute_deltas(base_ev: Dict[str, Any], opt_ev: Dict[str, Any]) -> Dict[str, Any]:
        f_b = base_ev["total_fuel_tonnes_hfo_eq"]
        f_o = opt_ev["total_fuel_tonnes_hfo_eq"]
        f_diff = f_o - f_b
        f_pct = (f_diff / max(1e-4, f_b)) * 100.0

        c_b = base_ev["total_operating_cost_usd"]
        c_o = opt_ev["total_operating_cost_usd"]
        c_diff = c_o - c_b
        c_pct = (c_diff / max(1e-4, c_b)) * 100.0

        e_b = base_ev["total_emissions_co2e_tonnes"]
        e_o = opt_ev["total_emissions_co2e_tonnes"]
        e_diff = e_o - e_b
        e_pct = (e_diff / max(1e-4, e_b)) * 100.0

        ci_b = base_ev["carbon_intensity_g_tnm"]
        ci_o = opt_ev["carbon_intensity_g_tnm"]
        ci_diff = ci_o - ci_b
        ci_pct = (ci_diff / max(1e-4, ci_b)) * 100.0

        return {
            "fuel_delta_t": round(f_diff, 1),
            "fuel_delta_pct": round(f_pct, 2),
            "fuel_label": format_signed_change(f_diff, f_pct, "tonnes"),
            "cost_delta_usd": round(c_diff, 0),
            "cost_delta_pct": round(c_pct, 2),
            "cost_label": format_signed_change(c_diff, c_pct, "USD"),
            "emissions_delta_t": round(e_diff, 1),
            "emissions_delta_pct": round(e_pct, 2),
            "emissions_label": format_signed_change(e_diff, e_pct, "t CO2e"),
            "ci_delta_g_tnm": round(ci_diff, 2),
            "ci_delta_pct": round(ci_pct, 2),
            "ci_label": format_signed_change(ci_diff, ci_pct, "g/t-nm"),
        }

    deltas_vs_naive = compute_deltas(naive_eval, optimized_eval)
    deltas_vs_conv = compute_deltas(best_conv_eval, optimized_eval)

    summary = {
        "naive": {
            "fuel_t": round(naive_eval["total_fuel_tonnes_hfo_eq"], 1),
            "cost_usd": round(naive_eval["total_operating_cost_usd"], 0),
            "emissions_t": round(naive_eval["total_emissions_co2e_tonnes"], 1),
            "ci_g_tnm": round(naive_eval["carbon_intensity_g_tnm"], 2),
            "feasible": naive_eval["is_feasible"],
            "violations": naive_eval["constraint_violations"],
        },
        "best_conventional": {
            "fuel_t": round(best_conv_eval["total_fuel_tonnes_hfo_eq"], 1),
            "cost_usd": round(best_conv_eval["total_operating_cost_usd"], 0),
            "emissions_t": round(best_conv_eval["total_emissions_co2e_tonnes"], 1),
            "ci_g_tnm": round(best_conv_eval["carbon_intensity_g_tnm"], 2),
            "feasible": best_conv_eval["is_feasible"],
            "violations": best_conv_eval["constraint_violations"],
        },
        "optimized": {
            "fuel_t": round(optimized_eval["total_fuel_tonnes_hfo_eq"], 1),
            "cost_usd": round(optimized_eval["total_operating_cost_usd"], 0),
            "emissions_t": round(optimized_eval["total_emissions_co2e_tonnes"], 1),
            "ci_g_tnm": round(optimized_eval["carbon_intensity_g_tnm"], 2),
            "feasible": optimized_eval["is_feasible"],
            "violations": optimized_eval["constraint_violations"],
        },
        "vs_naive": deltas_vs_naive,
        "vs_best_conventional": deltas_vs_conv,
    }

    # 5. Detailed Route Allocation Table with Oversupply Ratios
    route_rows = []
    for r_key in problem.route_keys:
        r_cfg = cfg["routes"][r_key]
        n_det = naive_eval["route_details"][r_key]
        c_det = best_conv_eval["route_details"][r_key]
        o_det = optimized_eval["route_details"][r_key]

        route_rows.append(
            {
                "Route ID": r_key,
                "Route Name": r_cfg["name"],
                "Distance (nm)": r_cfg["distance_nm"],
                "Demand (TEU)": r_cfg["annual_demand_teu"],
                "Naive Speed (kn)": n_det["speed_knots"],
                "Best Conv Speed (kn)": c_det["speed_knots"],
                "Opt Speed (kn)": o_det["speed_knots"],
                "Naive Vessels": n_det["vessels_assigned"],
                "Best Conv Vessels": c_det["vessels_assigned"],
                "Opt Vessels": o_det["vessels_assigned"],
                "Naive Oversupply Ratio": n_det["oversupply_ratio"],
                "Best Conv Oversupply Ratio": c_det["oversupply_ratio"],
                "Opt Oversupply Ratio": o_det["oversupply_ratio"],
                "Naive Sailings/Wk": round(n_det["sailings_per_week"], 2),
                "Best Conv Sailings/Wk": round(c_det["sailings_per_week"], 2),
                "Opt Sailings/Wk": round(o_det["sailings_per_week"], 2),
                "Naive Reliability": round(n_det["reliability"], 2),
                "Best Conv Reliability": round(c_det["reliability"], 2),
                "Opt Reliability": round(o_det["reliability"], 2),
            }
        )
    df_routes = pd.DataFrame(route_rows)

    # 6. Monthly operational simulation
    df_monthly = simulate_monthly_operations(problem, naive_bits, best_conv_bits, optimized_bits)

    return {
        "summary": summary,
        "naive_eval": naive_eval,
        "best_conv_eval": best_conv_eval,
        "optimized_eval": optimized_eval,
        "naive_bits": naive_bits,
        "best_conv_bits": best_conv_bits,
        "optimized_bits": optimized_bits,
        "convergence_curve": opt_res["convergence_curve"],
        "df_routes": df_routes,
        "df_monthly": df_monthly,
        "evaluations": opt_res["evaluations"],
        "options": problem.options,
    }
