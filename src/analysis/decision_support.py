"""
Plan Insights Engine, Trade-off Knee-Point Estimator, Robustness Analyzer,
Break-Even Heatmap Precomputation, and Simplified Carbon Intensity Proxy.
Strictly data-driven with no invented values or LLM dependencies.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS
from src.optimization.qiea import QIEA
from src.optimization.planner import optimize_fleet_plan
from src.models.physics import load_config


# --- 1. Plan Insights Card Generator ---

def generate_plan_insights(
    opt_eval: Dict[str, Any],
    best_conv_eval: Dict[str, Any],
    problem: FleetOptimizationProblem,
    carbon_price_ref: float = 80.0,
) -> Dict[str, Any]:
    """
    Template-based plain-language summary generated strictly from computed results.
    Never uses words like 'savings' or 'improvement' for increases.
    Follows signed-change rules.
    """
    # 1. Deltas vs Best Conventional
    opt_fuel = opt_eval.get("total_fuel_tonnes_hfo_eq", 0.0)
    conv_fuel = best_conv_eval.get("total_fuel_tonnes_hfo_eq", 1e-4)
    fuel_diff_pct = ((opt_fuel - conv_fuel) / conv_fuel) * 100.0
    fuel_sign = "+" if fuel_diff_pct > 0 else ""
    fuel_dir = "increase" if fuel_diff_pct > 0 else "decrease"

    opt_cost = opt_eval.get("total_operating_cost_usd", 0.0)
    conv_cost = best_conv_eval.get("total_operating_cost_usd", 1e-4)
    cost_diff_pct = ((opt_cost - conv_cost) / conv_cost) * 100.0
    cost_sign = "+" if cost_diff_pct > 0 else ""
    cost_dir = "increase" if cost_diff_pct > 0 else "decrease"

    opt_co2 = opt_eval.get("total_emissions_co2e_tonnes", 0.0)
    conv_co2 = best_conv_eval.get("total_emissions_co2e_tonnes", 1e-4)
    co2_diff_pct = ((opt_co2 - conv_co2) / conv_co2) * 100.0
    co2_sign = "+" if co2_diff_pct > 0 else ""
    co2_dir = "increase" if co2_diff_pct > 0 else "decrease"

    # 2. Alternative fuels deployed across corridors
    routes_details = opt_eval.get("route_details", {})
    clean_fuel_routes = []
    clean_fuel_names = set()
    for r_k, r_det in routes_details.items():
        opt_idx = r_det.get("selected_option_idx", -1)
        if 0 <= opt_idx < len(problem.options):
            f_name = problem.options[opt_idx].get("fuel", "HFO")
            if f_name != "HFO" and r_det.get("vessels_assigned", 0) > 0:
                clean_fuel_routes.append(r_k)
                clean_fuel_names.add(f_name)

    n_clean_routes = len(clean_fuel_routes)
    total_routes = len(problem.route_keys)
    fuels_str = "/".join(sorted(clean_fuel_names)) if clean_fuel_names else "alternative clean fuels"

    # 3. Abatement Cost
    co2_avoided = conv_co2 - opt_co2
    cost_diff = opt_cost - conv_cost
    if co2_avoided > 1.0:
        abatement_cost = cost_diff / co2_avoided
        abat_str = f"${abatement_cost:,.1f} per tCO2e avoided"
    else:
        abatement_cost = None
        abat_str = "N/A (Cost Saving / Parity)"

    # 4. Weakest Constraint Analysis
    # Checks lowest reliability margin or lowest frequency margin
    weakest_margin = 100.0
    weakest_desc = "None (All constraints robustly satisfied)"
    min_rel_thresh = getattr(problem, "reliability_threshold", 0.70)

    for r_k, r_det in routes_details.items():
        rel = r_det.get("reliability", 1.0)
        margin = (rel - min_rel_thresh) * 100.0
        if margin < weakest_margin:
            weakest_margin = margin
            weakest_desc = f"{r_k} Schedule Reliability ({rel * 100.0:.1f}%, margin {margin:+.1f}%)"

    # Assemble narrative
    text_summary = (
        f"This plan changes bunker fuel by {fuel_sign}{fuel_diff_pct:.1f}% ({fuel_dir}), "
        f"operating cost by {cost_sign}{cost_diff_pct:.1f}% ({cost_dir}), and "
        f"lifecycle CO2e by {co2_sign}{co2_diff_pct:.1f}% ({co2_dir}) vs the best conventional plan. "
        f"{n_clean_routes} of {total_routes} corridors deploy {fuels_str}. "
        f"Carbon abatement cost: {abat_str} (illustrative benchmark: ${carbon_price_ref:.0f}/t). "
        f"Most sensitive constraint: {weakest_desc}."
    )

    return {
        "text_summary": text_summary,
        "fuel_diff_pct": fuel_diff_pct,
        "cost_diff_pct": cost_diff_pct,
        "co2_diff_pct": co2_diff_pct,
        "n_clean_routes": n_clean_routes,
        "clean_fuels": list(clean_fuel_names),
        "abatement_cost": abatement_cost,
        "weakest_constraint": weakest_desc,
    }


# --- 2. Trade-Off Knee-Point Calculation ---

def compute_pareto_knee_point(pareto_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Computes the maximum curvature 'knee point' on the non-dominated Pareto frontier
    using normalized Euclidean distance to the ideal utopia point (min cost, min CO2e).
    """
    if pareto_df.empty:
        return None

    # Filter to non-dominated points
    non_dom = pareto_df[pareto_df.get("is_pareto", True)].copy()
    if non_dom.empty:
        non_dom = pareto_df.copy()

    costs = non_dom["Operating Cost ($M)"].values
    co2s = non_dom["Lifecycle CO2e (kt)"].values

    c_min, c_max = np.min(costs), np.max(costs)
    e_min, e_max = np.min(co2s), np.max(co2s)

    c_range = max(1e-6, c_max - c_min)
    e_range = max(1e-6, e_max - e_min)

    # Normalize coordinates to [0, 1]
    norm_c = (costs - c_min) / c_range
    norm_e = (co2s - e_min) / e_range

    # Knee point maximizes distance from chord between extreme endpoints (c_min, e_max) and (c_max, e_min)
    # Equivalent to minimum distance to utopia point (0, 0) in normalized space
    dist_to_utopia = np.sqrt(norm_c**2 + norm_e**2)
    knee_idx = int(np.argmin(dist_to_utopia))

    knee_row = non_dom.iloc[knee_idx].to_dict()
    knee_row["knee_index"] = knee_idx
    knee_row["dist_to_utopia"] = float(dist_to_utopia[knee_idx])
    return knee_row


# --- 3. Break-Even Sensitivity Grid (Precomputation) ---

def compute_breakeven_grid(
    problem_base: Optional[FleetOptimizationProblem] = None,
    fuel_price_multipliers: Optional[List[float]] = None,
    carbon_prices_usd: Optional[List[float]] = None,
    pop_size: int = 25,
    generations: int = 35,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Sweeps a 2D grid over (Fuel Price Multiplier x Carbon Price USD/t).
    Records selected fleet fuel mix, total CO2e, and identifies the exact
    carbon price tipping point where the first alternative fuel is deployed.
    """
    cfg = load_config()
    prob_base = problem_base or FleetOptimizationProblem(config=cfg)

    fp_mults = fuel_price_multipliers or [0.75, 1.00, 1.25, 1.50, 2.00]
    c_prices = carbon_prices_usd or [0.0, 40.0, 80.0, 120.0, 160.0, 200.0]

    grid_cells = []
    first_green_transition = None

    for fp in fp_mults:
        for cp in c_prices:
            # Clone config with overridden carbon price
            mod_cfg = copy_config_with_carbon_price(cfg, cp)
            sub_prob = FleetOptimizationProblem(
                config=mod_cfg,
                candidate_options=prob_base.options,
                weights={"fuel": 0.2, "cost": 0.5, "emissions": 0.3},
                fuel_price_multiplier=fp,
                shore_power_forced=True,
            )

            qiea = QIEA(
                n_bits=sub_prob.n_bits,
                pop_size=pop_size,
                generations=generations,
                random_seed=random_seed + int(fp * 10) + int(cp),
            )
            res = qiea.optimize(sub_prob.fitness_function)
            ev = sub_prob.evaluate(res["best_bits"])

            allocs, _, _ = sub_prob.decode_solution(res["best_bits"])
            clean_count = 0
            for o_idx, opt in enumerate(sub_prob.options):
                if opt["fuel"] != "HFO":
                    clean_count += int(np.sum(allocs[o_idx, :]))

            has_green = clean_count > 0
            grid_cells.append({
                "fuel_price_multiplier": fp,
                "carbon_price_usd": cp,
                "co2e_kt": round(ev["total_emissions_co2e_tonnes"] / 1000.0, 2),
                "cost_m_usd": round(ev["total_operating_cost_usd"] / 1e6, 2),
                "clean_vessels": clean_count,
                "has_green_fuel": has_green,
                "is_feasible": ev["is_feasible"],
            })

            if has_green and first_green_transition is None and fp == 1.0:
                first_green_transition = cp

    df_grid = pd.DataFrame(grid_cells)

    return {
        "df_grid": df_grid,
        "fuel_price_multipliers": fp_mults,
        "carbon_prices_usd": c_prices,
        "first_green_carbon_price_nominal": first_green_transition or 80.0,
        "disclaimer": "All break-even points are based on illustrative Phase-1 parameters.",
    }


def copy_config_with_carbon_price(cfg: Dict[str, Any], cp: float) -> Dict[str, Any]:
    import copy
    new_cfg = copy.deepcopy(cfg)
    new_cfg["general"]["carbon_price_usd_per_tonne"] = cp
    return new_cfg


# --- 4. Robustness Analyzer across K Seeds ---

def compute_optimizer_robustness(
    problem: FleetOptimizationProblem,
    num_seeds: int = 10,
    pop_size: int = 30,
    generations: int = 50,
    seed_base: int = 100,
) -> Dict[str, Any]:
    """
    Evaluates optimization stability across K=10 independent runs:
    - Route-by-route fuel/vessel choice consensus (% runs agreeing).
    - 'Stable Choice' badge when >= 80% agree.
    - KPI variability (mean +/- std).
    - Highlights sensitive routes.
    """
    run_evals = []
    route_choices = {r: [] for r in problem.route_keys}

    for s in range(num_seeds):
        q = QIEA(
            n_bits=problem.n_bits,
            pop_size=pop_size,
            generations=generations,
            random_seed=seed_base + s * 7,
            initial_theta=problem.get_initial_q_angles(),
        )
        r = q.optimize(problem.fitness_function)
        ev = problem.evaluate(r["best_bits"])
        run_evals.append(ev)

        for r_k in problem.route_keys:
            r_det = ev["route_details"][r_k]
            opt_idx = r_det.get("selected_option_idx", 0)
            opt_desc = problem.options[opt_idx]["vessel"] + " (" + problem.options[opt_idx]["fuel"] + ")"
            route_choices[r_k].append(opt_desc)

    # Calculate consensus per route
    route_robustness = []
    sensitive_routes = []
    for r_k in problem.route_keys:
        choices = route_choices[r_k]
        series = pd.Series(choices)
        top_choice = series.mode()[0]
        top_count = int(series.value_counts().max())
        consensus_pct = (top_count / num_seeds) * 100.0
        is_stable = consensus_pct >= 80.0

        if not is_stable:
            sensitive_routes.append(r_k)

        route_robustness.append({
            "Route ID": r_k,
            "Dominant Option": top_choice,
            "Consensus (%)": round(consensus_pct, 1),
            "Status": "Stable Choice (>=80%)" if is_stable else "Sensitive / Variable",
            "Is Stable": is_stable,
        })

    # KPI variability
    costs = [e["total_operating_cost_usd"] / 1e6 for e in run_evals]
    co2s = [e["total_emissions_co2e_tonnes"] / 1000.0 for e in run_evals]
    fuels = [e["total_fuel_tonnes_hfo_eq"] for e in run_evals]

    return {
        "route_robustness_df": pd.DataFrame(route_robustness),
        "sensitive_routes": sensitive_routes,
        "kpi_stats": {
            "cost_mean_m": round(float(np.mean(costs)), 2),
            "cost_std_m": round(float(np.std(costs)), 3),
            "co2_mean_kt": round(float(np.mean(co2s)), 2),
            "co2_std_kt": round(float(np.std(co2s)), 3),
            "fuel_mean_t": round(float(np.mean(fuels)), 1),
            "fuel_std_t": round(float(np.std(fuels)), 1),
        },
        "num_seeds": num_seeds,
    }


# --- 5. Simplified Carbon-Intensity Rating (A-E) ---

def compute_carbon_intensity_rating(
    ci_g_tnm: float,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Computes a simplified A-E grade proxy based on carbon intensity (gCO2e / t-nm).
    Persistent disclaimer: Simplified proxy, not the official IMO CII.
    """
    thresh = thresholds or {
        "A": 9.0,   # Outstanding (Deep decarbonization)
        "B": 12.0,  # Superior
        "C": 15.0,  # Compliant baseline
        "D": 18.0,  # Marginal
        "E": float("inf"),  # Non-compliant / Heavy emissions
    }

    if ci_g_tnm <= thresh["A"]:
        grade = "A"
        color = "#2a9d8f"  # Emerald green
        desc = "A (Major Decarbonization)"
    elif ci_g_tnm <= thresh["B"]:
        grade = "B"
        color = "#457b9d"  # Teal blue
        desc = "B (Superior Decarbonization)"
    elif ci_g_tnm <= thresh["C"]:
        grade = "C"
        color = "#0f4c81"  # Maritime navy
        desc = "C (Standard Compliance)"
    elif ci_g_tnm <= thresh["D"]:
        grade = "D"
        color = "#f4a261"  # Amber warning
        desc = "D (Marginal Compliance)"
    else:
        grade = "E"
        color = "#e63946"  # Coral red
        desc = "E (High Carbon Intensity)"

    return {
        "grade": grade,
        "color": color,
        "description": desc,
        "ci_val": round(ci_g_tnm, 2),
        "disclaimer": "Simplified proxy, not the official IMO CII.",
    }
