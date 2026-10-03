"""
Comprehensive unit tests for FIX PASS 3 and ENHANCEMENT PASS:
- Baselines: best_conventional.objective <= naive.objective
- Optimization: selected_plan.objective <= best_conventional.objective
- Weight sensitivity: Min CO2e gives CO2e <= Min Cost; under weights 0.05/0.05/0.90 selected plan uses green fuel
- Artifact freshness & hash matching
- API validation: reliability in 0-100 range, no silent defaults
- AppTest smoke tests across all Streamlit pages (<10s)
- Enhancement features:
  - Plan Insights card signed text wording
  - Knee-point calculation on Pareto frontier
  - Break-even sensitivity grid shape & properties
  - QIEA recording Q-bit history determinism (fixed seed produces identical result)
"""

import pytest
import numpy as np
import os
import pickle
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.optimization.planner import optimize_fleet_plan
from src.analysis.case_study import get_naive_baseline, get_best_conventional_baseline, run_case_study
from src.analysis.decision_support import (
    generate_plan_insights,
    compute_pareto_knee_point,
    compute_breakeven_grid,
    compute_carbon_intensity_rating,
    compute_optimizer_robustness,
)
from src.utils.hashing import get_codebase_hash, check_artifact_staleness
from api.index import build_routes_df


@pytest.fixture
def problem():
    return FleetOptimizationProblem()


def test_baseline_hierarchy(problem):
    """best_conventional.objective <= naive.objective and selected_plan.objective <= best_conventional.objective."""
    _, naive_eval = get_naive_baseline(problem)
    _, best_conv_eval = get_best_conventional_baseline(problem, pop_size=20, generations=25, random_seed=42)

    assert best_conv_eval["fitness"] <= naive_eval["fitness"] + 1e-5

    plan = optimize_fleet_plan(
        problem=problem,
        weights={"w_fuel": 0.40, "w_cost": 0.40, "w_emissions": 0.20},
        num_qiea_starts=3,
        evals_per_start=1500,
    )
    assert plan["selected_plan"]["fitness"] <= best_conv_eval["fitness"] + 1e-5
    assert "plan" in plan["winner_status"].lower()


def test_weight_sensitivity(problem):
    """
    Min CO2e preset must give CO2e <= Min Cost preset and cost >= Min Cost preset.
    Under green weights (0.05/0.05/0.90), the selected plan uses at least one non-HFO fuel.
    """
    cost_plan_res = optimize_fleet_plan(
        problem=problem,
        weights={"fuel": 0.10, "cost": 0.85, "emissions": 0.05},
        num_qiea_starts=3,
        evals_per_start=2000,
    )
    co2_plan_res = optimize_fleet_plan(
        problem=problem,
        weights={"fuel": 0.05, "cost": 0.05, "emissions": 0.90},
        num_qiea_starts=3,
        evals_per_start=2000,
    )

    cost_eval = cost_plan_res["selected_plan"]
    co2_eval = co2_plan_res["selected_plan"]

    assert co2_eval["total_emissions_co2e_tonnes"] <= cost_eval["total_emissions_co2e_tonnes"] + 1e-3
    assert co2_eval["total_operating_cost_usd"] >= cost_eval["total_operating_cost_usd"] - 1e-3

    # Check that under green weights, at least one non-HFO fuel is assigned
    allocs, _, _ = problem.decode_solution(co2_plan_res["selected_bits"])
    non_hfo_assigned = False
    for o_idx, opt in enumerate(problem.options):
        if opt["fuel"] != "HFO" and np.sum(allocs[o_idx, :]) > 0:
            non_hfo_assigned = True
            break
    assert non_hfo_assigned, "Green weights (0.05/0.05/0.90) did not activate any alternative clean fuel."


def test_pkl_hash_freshness():
    """All generated pkl files in data/ must store the exact current code hash."""
    curr_hash = get_codebase_hash()
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    pkl_files = [f for f in os.listdir(data_dir) if f.endswith(".pkl")]
    assert len(pkl_files) > 0, "No pickle files found in data/ directory."

    for pkl_file in pkl_files:
        path = os.path.join(data_dir, pkl_file)
        with open(path, "rb") as f:
            content = pickle.load(f)
        if isinstance(content, dict) and "code_hash" in content:
            stored_hash = content["code_hash"]
            assert stored_hash == curr_hash, f"Stale hash in {pkl_file}: {stored_hash} != {curr_hash}"


def test_api_reliability_range_and_no_synthetic_defaults():
    """API reliability must be in range [0, 100] (%) and empty allocations must not generate phantom vessels."""
    problem = FleetOptimizationProblem()
    zero_bits = np.zeros(problem.n_bits, dtype=int)
    eval_res = problem.evaluate(zero_bits)

    routes_df = build_routes_df(problem, eval_res)
    for route in routes_df:
        assert 0.0 <= route["reliability"] <= 100.0
        assert route["vessels"] == 0
        assert route["fuel"] is None or route["fuel"] == "None"


def test_apptest_smoke_all_pages():
    """Streamlit AppTest smoke tests across all pages (<10s, no exceptions)."""
    app_dir = os.path.join(os.path.dirname(__file__), "..", "app")
    
    # 1. Home
    at_home = AppTest.from_file(os.path.join(app_dir, "Home.py"), default_timeout=10)
    at_home.run()
    assert not at_home.exception, f"Home.py raised an exception: {at_home.exception}"

    # 2. Pages
    pages = [
        "1_Fuel_Predictor.py",
        "2_Alternative_Fuels.py",
        "3_Shore_Power.py",
        "4_Scenarios.py",
        "5_Benchmark.py",
        "6_Case_Study.py",
        "7_About_and_Method.py",
    ]
    for page in pages:
        page_path = os.path.join(app_dir, "pages", page)
        at = AppTest.from_file(page_path, default_timeout=10)
        at.run()
        assert not at.exception, f"Page {page} raised an exception: {at.exception}"


def test_plan_insights_wording_rules(problem):
    """Plan Insights generator must follow strict signed change formatting and contain no forbidden wording."""
    _, naive_eval = get_naive_baseline(problem)
    _, best_conv_eval = get_best_conventional_baseline(problem, pop_size=15, generations=20, random_seed=42)

    insights = generate_plan_insights(naive_eval, best_conv_eval, problem, carbon_price_ref=80.0)
    summary_text = insights["text_summary"]

    assert "This plan changes" in summary_text
    assert "increase" in summary_text or "decrease" in summary_text or "no change" in summary_text
    assert "savings" not in summary_text.lower()
    assert "improvement" not in summary_text.lower()


def test_knee_point_calculation():
    """Knee-point calculation must return the point on the Pareto front closest to the normalized ideal point."""
    df_sample = pd.DataFrame([
        {"Operating Cost ($M)": 10.0, "Lifecycle CO2e (kt)": 100.0, "is_pareto": True},
        {"Operating Cost ($M)": 15.0, "Lifecycle CO2e (kt)": 40.0, "is_pareto": True},  # Obvious knee
        {"Operating Cost ($M)": 30.0, "Lifecycle CO2e (kt)": 35.0, "is_pareto": True},
        {"Operating Cost ($M)": 50.0, "Lifecycle CO2e (kt)": 32.0, "is_pareto": True},
    ])
    knee = compute_pareto_knee_point(df_sample)
    assert knee is not None
    assert knee["Operating Cost ($M)"] == 15.0
    assert knee["Lifecycle CO2e (kt)"] == 40.0


def test_breakeven_grid_structure(problem):
    """Break-even grid generator produces valid grid dimensions and identifies a positive tipping point."""
    grid_res = compute_breakeven_grid(
        problem_base=problem,
        fuel_price_multipliers=[1.0, 1.5],
        carbon_prices_usd=[0.0, 80.0, 160.0],
        pop_size=15,
        generations=15,
        random_seed=42,
    )
    df_grid = grid_res["df_grid"]
    assert len(df_grid) == 2 * 3
    assert "co2e_kt" in df_grid.columns
    assert "has_green_fuel" in df_grid.columns
    assert grid_res["first_green_carbon_price_nominal"] >= 0.0


def test_qiea_recording_determinism(problem):
    """Enabling record_q_history must NOT alter the optimization best bits or best fitness for a fixed seed."""
    seed = 42
    q1 = QIEA(n_bits=problem.n_bits, pop_size=15, generations=20, random_seed=seed, record_q_history=False)
    res1 = q1.optimize(problem.fitness_function)

    q2 = QIEA(n_bits=problem.n_bits, pop_size=15, generations=20, random_seed=seed, record_q_history=True)
    res2 = q2.optimize(problem.fitness_function)

    assert np.array_equal(res1["best_bits"], res2["best_bits"])
    assert res1["best_fitness"] == res2["best_fitness"]
    assert "q_prob_history" in res2
    assert len(res2["q_prob_history"]) == 20
