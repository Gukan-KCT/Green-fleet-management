"""
Unit tests for QIEA determinism, optimization sanity vs random baseline, Pareto filtering,
oversupply carbon intensity behavior, and superiority over best conventional baseline.
"""

import pytest
import numpy as np
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.optimization.baselines import RandomSearch
from src.optimization.pareto import filter_non_dominated
from src.analysis.case_study import get_naive_baseline, get_best_conventional_baseline


@pytest.fixture
def problem():
    return FleetOptimizationProblem()


def test_qiea_determinism(problem):
    """Running QIEA twice with the exact same seed must produce identical bitstrings and convergence curves."""
    seed = 12345
    q1 = QIEA(
        n_bits=problem.n_bits,
        pop_size=15,
        generations=20,
        random_seed=seed,
        initial_theta=problem.get_initial_q_angles(),
    )
    res1 = q1.optimize(problem.fitness_function)

    q2 = QIEA(
        n_bits=problem.n_bits,
        pop_size=15,
        generations=20,
        random_seed=seed,
        initial_theta=problem.get_initial_q_angles(),
    )
    res2 = q2.optimize(problem.fitness_function)

    # Identical solutions
    assert np.array_equal(res1["best_bits"], res2["best_bits"])
    assert res1["best_fitness"] == res2["best_fitness"]
    assert np.allclose(res1["convergence_curve"], res2["convergence_curve"])


def test_qiea_vs_random_baseline(problem):
    """QIEA must achieve a superior (lower) penalized fitness than uniform random search on the case study."""
    pop = 20
    gens = 25
    seed = 42

    # QIEA
    q = QIEA(
        n_bits=problem.n_bits,
        pop_size=pop,
        generations=gens,
        random_seed=seed,
        initial_theta=problem.get_initial_q_angles(),
    )
    res_q = q.optimize(problem.fitness_function)

    # Random Search with identical total evaluation budget
    rs = RandomSearch(
        n_bits=problem.n_bits,
        evaluations_per_generation=pop,
        generations=gens,
        random_seed=seed,
    )
    res_rs = rs.optimize(problem.fitness_function)

    # Lower fitness is better
    assert res_q["best_fitness"] < res_rs["best_fitness"]


def test_pareto_filter():
    """Verify non-dominated filtering logic in 3-objective space."""
    sols = [
        {"id": "A", "total_fuel_gj": 100, "total_operating_cost_usd": 100, "total_emissions_co2e_tonnes": 100, "is_feasible": True},
        {"id": "B", "total_fuel_gj": 90,  "total_operating_cost_usd": 110, "total_emissions_co2e_tonnes": 105, "is_feasible": True},
        {"id": "C", "total_fuel_gj": 120, "total_operating_cost_usd": 120, "total_emissions_co2e_tonnes": 120, "is_feasible": True},  # Dominated by A
        {"id": "D", "total_fuel_gj": 95,  "total_operating_cost_usd": 95,  "total_emissions_co2e_tonnes": 95,  "is_feasible": True},  # Dominates A
    ]

    p_front = filter_non_dominated(sols)
    p_ids = [s["id"] for s in p_front]

    assert "C" not in p_ids  # C is dominated by both A and D
    assert "A" not in p_ids  # A is dominated by D
    assert "D" in p_ids
    assert "B" in p_ids


def test_oversupply_does_not_reduce_carbon_intensity(problem):
    """
    CRITICAL MODELING RULE:
    Transport work must use cargo actually moved = min(route capacity, demand) x distance.
    Adding excess ships to an already demand-satisfied route increases fuel and emissions
    while keeping transport work constant, which must NEVER reduce carbon intensity.
    """
    base_bits, base_eval = get_naive_baseline(problem)
    assert base_eval["is_feasible"]

    base_ci = base_eval["carbon_intensity_g_tnm"]
    base_work = base_eval["total_transport_work_tnm"]

    # Construct oversupplied bits: add 1 more handymax vessel to R1 (where demand was already met)
    oversupplied_bits = np.copy(base_bits)
    r1_idx = problem.route_keys.index("R1")
    idx = 2 * (2 * len(problem.route_keys) + r1_idx)
    oversupplied_bits[idx] = 1
    oversupplied_bits[idx + 1] = 1  # 3 vessels instead of 2

    over_eval = problem.evaluate(oversupplied_bits)
    over_ci = over_eval["carbon_intensity_g_tnm"]
    over_work = over_eval["total_transport_work_tnm"]

    # Transport work must remain unchanged because demand was already fully met
    assert np.isclose(over_work, base_work, rtol=1e-4)
    # Carbon intensity must strictly increase due to extra unnecessary emissions
    assert over_ci > base_ci, f"Oversupplying ships reduced CI: {over_ci:.2f} vs {base_ci:.2f}"


def test_optimized_not_worse_than_best_conventional(problem):
    """
    The optimized green fleet plan must never perform worse in composite fitness
    than the best feasible conventional baseline.
    """
    best_conv_bits, best_conv_eval = get_best_conventional_baseline(
        problem=problem, pop_size=25, generations=40, random_seed=42
    )
    assert best_conv_eval["is_feasible"]

    # Run optimizer seeded with best conventional baseline
    qiea = QIEA(
        n_bits=problem.n_bits,
        pop_size=25,
        generations=40,
        random_seed=42,
        initial_theta=problem.get_initial_q_angles(),
    )
    opt_res = qiea.optimize(problem.fitness_function, seed_bits=best_conv_bits)
    opt_eval = problem.evaluate(opt_res["best_bits"])

    assert opt_eval["is_feasible"]
    assert opt_eval["fitness"] <= best_conv_eval["fitness"] + 1e-6
