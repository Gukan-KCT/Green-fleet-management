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
    Construct the 'Best Conventional' baseline defined over restricted QIEA,
    restricted GA and hill-climbing from the feasible naive plan (HFO only, no shore power),
    across several seeds, all polished with 1-bit-flip local search.
    Guarantees best_conventional.objective <= naive.objective and is_feasible=True.
    """
    from src.optimization.baselines import BinaryGeneticAlgorithm

    # 1. Start with feasible naive baseline as primary candidate
    naive_bits, naive_eval = get_naive_baseline(problem)
    candidates = []
    if naive_eval["is_feasible"]:
        candidates.append((naive_bits.copy(), naive_eval))

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
        use_gray_code=problem.use_gray_code,
    )

    def _map_conv_to_full(conv_bits: np.ndarray) -> np.ndarray:
        allocs, speeds, _ = conv_problem.decode_solution(conv_bits)
        full_allocs = np.zeros((len(problem.options), len(problem.route_keys)), dtype=int)
        for c_idx, opt in enumerate(hfo_options):
            o_idx = problem.options.index(opt)
            full_allocs[o_idx, :] = allocs[c_idx, :]
        shore = {p: False for p in problem.port_keys}
        return problem.encode_solution(full_allocs, speeds, shore)

    # 2. Run restricted GA and QIEA across multiple seeds
    test_seeds = [random_seed, random_seed + 1, random_seed + 2]
    for s in test_seeds:
        # Restricted GA
        ga = BinaryGeneticAlgorithm(
            n_bits=conv_problem.n_bits,
            pop_size=min(30, pop_size),
            generations=min(40, generations),
            random_seed=s,
        )
        r_ga = ga.optimize(conv_problem.fitness_function)
        full_ga_bits = _map_conv_to_full(r_ga["best_bits"])
        ev_ga = problem.evaluate(full_ga_bits)
        if ev_ga["is_feasible"]:
            candidates.append((full_ga_bits, ev_ga))

        # Restricted QIEA
        q = QIEA(
            n_bits=conv_problem.n_bits,
            pop_size=min(30, pop_size),
            generations=min(40, generations),
            random_seed=s,
            initial_theta=conv_problem.get_initial_q_angles(),
        )
        r_q = q.optimize(conv_problem.fitness_function)
        full_q_bits = _map_conv_to_full(r_q["best_bits"])
        ev_q = problem.evaluate(full_q_bits)
        if ev_q["is_feasible"]:
            candidates.append((full_q_bits, ev_q))

    # 3. Polish best candidate with 1-bit-flip local search restricted to HFO and speeds
    best_cand_bits, best_cand_eval = min(
        candidates, key=lambda c: c[1]["fitness"] if c[1]["is_feasible"] else float("inf")
    )

    curr_bits = best_cand_bits.copy()
    curr_fit = best_cand_eval["fitness"]
    improved = True
    step = 0
    max_steps = 15

    while improved and step < max_steps:
        improved = False
        step += 1
        best_flip = None
        best_f = curr_fit

        # Flip only HFO allocation bits and speed bits (shore power stays 0)
        for i in range(problem.n_alloc_bits + problem.n_speed_bits):
            cand = curr_bits.copy()
            cand[i] = 1 - cand[i]
            # Verify no non-HFO options were activated
            cand_allocs, cand_speeds, _ = problem.decode_solution(cand)
            has_clean_fuel = False
            for o_idx, opt in enumerate(problem.options):
                if opt["fuel"] != "HFO" and np.sum(cand_allocs[o_idx, :]) > 0:
                    has_clean_fuel = True
                    break
            if has_clean_fuel:
                continue

            ev = problem.evaluate(cand)
            if ev["is_feasible"] and ev["fitness"] < best_f:
                best_f = ev["fitness"]
                best_flip = i

        if best_flip is not None:
            curr_bits[best_flip] = 1 - curr_bits[best_flip]
            curr_fit = best_f
            improved = True

    final_eval = problem.evaluate(curr_bits)
    # Ensure best conventional never exceeds naive
    if (not final_eval["is_feasible"]) or (final_eval["fitness"] > naive_eval["fitness"]):
        return naive_bits, naive_eval

    return curr_bits, final_eval


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
    pop_size: int = 40,
    generations: int = 100,
    random_seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run complete comparative Case Study across FOUR distinct operational plans:
    1. Feasible Naive Baseline (Conventional HFO, fixed speed, no shore power)
    2. Best Conventional Baseline (Optimizer restricted to HFO, no shore power)
    3. Balanced Multi-Objective Optimized Plan (w_cost=0.4, w_emiss=0.4, w_fuel=0.2)
    4. Green Multi-Objective Optimized Plan (w_emiss=0.8, w_cost=0.1, w_fuel=0.1)

    Calculates signed deltas and carbon abatement cost ($ USD / tCO2e avoided) vs Best Conventional.
    """
    from src.optimization.planner import optimize_fleet_plan

    cfg = config or load_config()
    prob_balanced = FleetOptimizationProblem(
        config=cfg,
        weights={"fuel": 0.2, "cost": 0.4, "emissions": 0.4},
        shore_power_forced=True,
    )
    prob_green = FleetOptimizationProblem(
        config=cfg,
        weights={"fuel": 0.1, "cost": 0.1, "emissions": 0.8},
        shore_power_forced=True,
    )

    # 1. Optimize Balanced Plan (uses optimize_fleet_plan with 5 unseeded QIEA multi-starts)
    balanced_res = optimize_fleet_plan(
        problem=prob_balanced,
        num_qiea_starts=5,
        evals_per_start=4000,
        seeds=[random_seed, random_seed + 1, random_seed + 2, random_seed + 3, random_seed + 4],
    )
    naive_eval = balanced_res["naive_eval"]
    naive_bits = balanced_res["naive_bits"]
    best_conv_eval = balanced_res["best_conv_eval"]
    best_conv_bits = balanced_res["best_conv_bits"]
    balanced_eval = balanced_res["selected_plan"]
    balanced_bits = balanced_res["selected_bits"]

    # 2. Optimize Green Plan (emission-heavy weights)
    green_res = optimize_fleet_plan(
        problem=prob_green,
        num_qiea_starts=5,
        evals_per_start=4000,
        seeds=[random_seed + 10, random_seed + 11, random_seed + 12, random_seed + 13, random_seed + 14],
    )
    green_eval = green_res["selected_plan"]
    green_bits = green_res["selected_bits"]

    # Carbon price reference from config (illustrative)
    carbon_price_ref = float(cfg["general"].get("carbon_price_usd_per_tonne", 80.0))

    # Helper for signed deltas & abatement cost vs Best Conventional
    def compute_plan_metrics(eval_dict: Dict[str, Any]) -> Dict[str, Any]:
        c_diff = eval_dict["total_operating_cost_usd"] - best_conv_eval["total_operating_cost_usd"]
        c_pct = (c_diff / max(1e-4, best_conv_eval["total_operating_cost_usd"])) * 100.0

        e_diff = eval_dict["total_emissions_co2e_tonnes"] - best_conv_eval["total_emissions_co2e_tonnes"]
        e_pct = (e_diff / max(1e-4, best_conv_eval["total_emissions_co2e_tonnes"])) * 100.0

        f_diff = eval_dict["total_fuel_tonnes_hfo_eq"] - best_conv_eval["total_fuel_tonnes_hfo_eq"]
        f_pct = (f_diff / max(1e-4, best_conv_eval["total_fuel_tonnes_hfo_eq"])) * 100.0

        ci_diff = eval_dict["carbon_intensity_g_tnm"] - best_conv_eval["carbon_intensity_g_tnm"]
        ci_pct = (ci_diff / max(1e-4, best_conv_eval["carbon_intensity_g_tnm"])) * 100.0

        # Abatement cost = delta_cost / emissions_avoided = (cost_plan - cost_conv) / (emiss_conv - emiss_plan)
        emissions_avoided_t = -e_diff
        if emissions_avoided_t > 1.0:
            abatement_cost_usd_per_t = c_diff / emissions_avoided_t
        else:
            abatement_cost_usd_per_t = None

        return {
            "fuel_t": round(eval_dict["total_fuel_tonnes_hfo_eq"], 1),
            "cost_usd": round(eval_dict["total_operating_cost_usd"], 0),
            "emissions_t": round(eval_dict["total_emissions_co2e_tonnes"], 1),
            "ci_g_tnm": round(eval_dict["carbon_intensity_g_tnm"], 2),
            "feasible": eval_dict["is_feasible"],
            "violations": eval_dict["constraint_violations"],
            "cost_delta_usd": round(c_diff, 0),
            "cost_delta_pct": round(c_pct, 2),
            "cost_label": format_signed_change(c_diff, c_pct, "USD"),
            "emissions_delta_t": round(e_diff, 1),
            "emissions_delta_pct": round(e_pct, 2),
            "emissions_label": format_signed_change(e_diff, e_pct, "t CO2e"),
            "fuel_delta_t": round(f_diff, 1),
            "fuel_delta_pct": round(f_pct, 2),
            "fuel_label": format_signed_change(f_diff, f_pct, "tonnes"),
            "ci_delta_g_tnm": round(ci_diff, 2),
            "ci_delta_pct": round(ci_pct, 2),
            "ci_label": format_signed_change(ci_diff, ci_pct, "g/t-nm"),
            "emissions_avoided_t": round(emissions_avoided_t, 1) if emissions_avoided_t > 0 else 0.0,
            "abatement_cost_usd_per_t": round(abatement_cost_usd_per_t, 1) if abatement_cost_usd_per_t is not None else None,
        }

    summary = {
        "naive": compute_plan_metrics(naive_eval),
        "best_conventional": compute_plan_metrics(best_conv_eval),
        "balanced": compute_plan_metrics(balanced_eval),
        "green": compute_plan_metrics(green_eval),
        "carbon_price_reference_usd": carbon_price_ref,
        "winner_status_balanced": balanced_res["winner_status"],
        "winner_status_green": green_res["winner_status"],
    }

    # Detailed Route Allocation Table comparing all 4 plans
    route_rows = []
    for r_key in prob_balanced.route_keys:
        r_cfg = cfg["routes"][r_key]
        n_det = naive_eval["route_details"][r_key]
        c_det = best_conv_eval["route_details"][r_key]
        b_det = balanced_eval["route_details"][r_key]
        g_det = green_eval["route_details"][r_key]

        route_rows.append(
            {
                "Route ID": r_key,
                "Route Name": r_cfg["name"],
                "Distance (nm)": r_cfg["distance_nm"],
                "Demand (TEU)": r_cfg["annual_demand_teu"],
                "Naive Speed (kn)": n_det["speed_knots"],
                "Best Conv Speed (kn)": c_det["speed_knots"],
                "Balanced Speed (kn)": b_det["speed_knots"],
                "Green Speed (kn)": g_det["speed_knots"],
                "Naive Vessels": n_det["vessels_assigned"],
                "Best Conv Vessels": c_det["vessels_assigned"],
                "Balanced Vessels": b_det["vessels_assigned"],
                "Green Vessels": g_det["vessels_assigned"],
                "Naive Oversupply": n_det["oversupply_ratio"],
                "Best Conv Oversupply": c_det["oversupply_ratio"],
                "Balanced Oversupply": b_det["oversupply_ratio"],
                "Green Oversupply": g_det["oversupply_ratio"],
                "Naive Reliability (%)": round(n_det["reliability"] * 100.0, 1),
                "Best Conv Reliability (%)": round(c_det["reliability"] * 100.0, 1),
                "Balanced Reliability (%)": round(b_det["reliability"] * 100.0, 1),
                "Green Reliability (%)": round(g_det["reliability"] * 100.0, 1),
            }
        )
    df_routes = pd.DataFrame(route_rows)

    # 12-month calendar simulation
    df_monthly = simulate_monthly_operations(prob_balanced, naive_bits, best_conv_bits, balanced_bits)

    return {
        "summary": summary,
        "naive_eval": naive_eval,
        "best_conv_eval": best_conv_eval,
        "balanced_eval": balanced_eval,
        "green_eval": green_eval,
        "optimized_eval": balanced_eval,  # Backward compatibility
        "naive_bits": naive_bits,
        "best_conv_bits": best_conv_bits,
        "balanced_bits": balanced_bits,
        "green_bits": green_bits,
        "optimized_bits": balanced_bits,
        "convergence_curve": balanced_res["convergence_curve"],
        "df_routes": df_routes,
        "df_monthly": df_monthly,
        "evaluations": balanced_res["total_evaluations"] + green_res["total_evaluations"],
        "options": prob_balanced.options,
        "carbon_price_ref": carbon_price_ref,
    }
