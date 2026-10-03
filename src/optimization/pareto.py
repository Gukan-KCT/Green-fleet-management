"""
Pareto Multi-Objective Analysis via Weighted-Sum Grid Sweep and Non-Dominated Filtering.

Phase-1 Multi-Objective Implementation:
1. Systematically sweeps objective weight triads (w_fuel, w_cost, w_emissions) summing to 1.0.
2. Runs the optimization engine for each triad to generate diverse candidate policies.
3. Computes the 3-dimensional Pareto frontier by filtering out dominated solutions:
   Solution A dominates B iff:
     for all obj in {Fuel, Cost, Emissions}: obj(A) <= obj(B)
     and exists obj: obj(A) < obj(B).
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA


def get_default_weight_grid() -> List[Tuple[float, float, float]]:
    """
    Standard grid of weight triads spanning extreme trade-offs and balanced compromises.
    """
    return [
        (0.80, 0.10, 0.10),  # Extreme Fuel minimization
        (0.10, 0.80, 0.10),  # Extreme Cost minimization
        (0.10, 0.10, 0.80),  # Extreme Emissions decarbonization
        (0.34, 0.33, 0.33),  # Balanced tripartite compromise
        (0.50, 0.50, 0.00),  # Cost + Fuel focus (zero carbon weight)
        (0.50, 0.00, 0.50),  # Fuel + Emissions focus
        (0.00, 0.50, 0.50),  # Cost + Emissions focus
        (0.40, 0.40, 0.20),  # Commercial bias
        (0.20, 0.40, 0.40),  # Eco-commercial balance
        (0.40, 0.20, 0.40),  # Energy transition posture
    ]


def filter_non_dominated(solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter a list of solution dictionaries to return only non-dominated (Pareto optimal) points.
    Considers 3 objectives to minimize:
    - total_fuel_gj
    - total_operating_cost_usd
    - total_emissions_co2e_tonnes
    """
    if not solutions:
        return []

    # Prioritize feasible solutions
    feasible_solutions = [s for s in solutions if s.get("is_feasible", False)]
    candidate_pool = feasible_solutions if feasible_solutions else solutions

    pareto_front = []

    for i, a in enumerate(candidate_pool):
        a_dominated = False
        a_fuel = a["total_fuel_gj"]
        a_cost = a["total_operating_cost_usd"]
        a_emiss = a["total_emissions_co2e_tonnes"]

        for j, b in enumerate(candidate_pool):
            if i == j:
                continue

            b_fuel = b["total_fuel_gj"]
            b_cost = b["total_operating_cost_usd"]
            b_emiss = b["total_emissions_co2e_tonnes"]

            # Does b dominate a?
            # b is <= a on all criteria AND strictly < on at least one
            if (b_fuel <= a_fuel and b_cost <= a_cost and b_emiss <= a_emiss) and (
                b_fuel < a_fuel or b_cost < a_cost or b_emiss < a_emiss
            ):
                a_dominated = True
                break

        if not a_dominated:
            pareto_front.append(a)

    return pareto_front


def sweep_pareto_front(
    problem_base: Optional[FleetOptimizationProblem] = None,
    weight_grid: Optional[List[Tuple[float, float, float]]] = None,
    pop_size: int = 15,
    generations: int = 25,
    random_seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Execute multi-objective sweep over weight grid.
    Returns:
        (all_evaluated_solutions, pareto_optimal_front)
    """
    if problem_base is None:
        problem_base = FleetOptimizationProblem()

    weights_list = weight_grid or get_default_weight_grid()
    all_solutions = []

    for idx, (w_f, w_c, w_e) in enumerate(weights_list):
        prob = FleetOptimizationProblem(
            config=problem_base.config,
            candidate_options=problem_base.options,
            routes_override=problem_base.routes,
            weights={"fuel": w_f, "cost": w_c, "emissions": w_e},
            fuel_price_multiplier=problem_base.fuel_price_multiplier,
            demand_multiplier=problem_base.demand_multiplier,
            weather_multiplier=problem_base.weather_multiplier,
            speed_cap_delta=problem_base.speed_cap_delta,
            shore_power_forced=problem_base.shore_power_forced,
            carbon_intensity_cap=problem_base.carbon_intensity_cap,
        )

        opt = QIEA(
            n_bits=prob.n_bits,
            pop_size=pop_size,
            generations=generations,
            random_seed=random_seed + idx,
            initial_theta=prob.get_initial_q_angles(),
        )

        res = opt.optimize(prob.fitness_function)
        eval_result = prob.evaluate(res["best_bits"])
        eval_result["weights"] = {"fuel": w_f, "cost": w_c, "emissions": w_e}
        eval_result["weight_label"] = f"F:{w_f:.2f} C:{w_c:.2f} E:{w_e:.2f}"
        eval_result["best_bits"] = res["best_bits"]
        all_solutions.append(eval_result)

    pareto_front = filter_non_dominated(all_solutions)
    return all_solutions, pareto_front
