"""
Comprehensive unit tests for FIX PASS 3:
- Baselines: best_conventional.objective <= naive.objective
- Optimization: selected_plan.objective <= best_conventional.objective
- Weight sensitivity: Min CO2e gives CO2e <= Min Cost; under weights 0.05/0.05/0.90 selected plan uses green fuel
- Artifact freshness & hash matching
- API validation: reliability in 0-100 range, no silent defaults
- AppTest smoke tests across all Streamlit pages (<10s)
"""

import pytest
import numpy as np
import os
import pickle
from streamlit.testing.v1 import AppTest

from src.optimization.problem import FleetOptimizationProblem
from src.optimization.planner import optimize_fleet_plan
from src.analysis.case_study import get_naive_baseline, get_best_conventional_baseline, run_case_study
from src.utils.hashing import get_codebase_hash, check_artifact_staleness, CURRENT_CODE_HASH
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
        n_seeds=3,
        pop_size=15,
        generations=20,
    )
    assert plan["objective"] <= best_conv_eval["fitness"] + 1e-5
    assert plan["winner"] in ["green", "conventional"]


def test_weight_sensitivity(problem):
    """
    Min CO2e preset must give CO2e <= Min Cost preset and cost >= Min Cost preset.
    Under green weights (0.05/0.05/0.90), the selected plan uses at least one non-HFO fuel.
    """
    cost_plan = optimize_fleet_plan(
        problem=problem,
        weights={"w_fuel": 0.10, "w_cost": 0.85, "w_emissions": 0.05},
        n_seeds=3,
        pop_size=15,
        generations=25,
    )

    co2_plan = optimize_fleet_plan(
        problem=problem,
        weights={"w_fuel": 0.05, "w_cost": 0.05, "w_emissions": 0.90},
        n_seeds=3,
        pop_size=15,
        generations=25,
    )

    assert co2_plan["emissions_tco2e"] <= cost_plan["emissions_tco2e"] + 1e-3
    assert co2_plan["cost_usd"] >= cost_plan["cost_usd"] - 1e-3

    # Check that under green weights, at least one non-HFO fuel is assigned
    allocations = co2_plan["allocations"]
    non_hfo_assigned = any(
        alloc.get("vessels", 0) > 0 and alloc.get("fuel", "HFO") != "HFO"
        for alloc in allocations
    )
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

    routes_df = build_routes_df(eval_res, problem)
    for route in routes_df:
        assert 0.0 <= route["reliability"] <= 100.0
        # When 0 vessels assigned, vessels must be 0 and fuel must be None / "None"
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
        "1_Demand_Matrix.py",
        "2_Fleet_Specifications.py",
        "3_Emission_Factors.py",
        "4_Route_Network.py",
        "5_Benchmark.py",
        "6_Case_Study.py",
        "7_Sensitivity_Analysis.py",
        "8_Carbon_Tax_Explorer.py",
    ]
    for page in pages:
        page_path = os.path.join(app_dir, "pages", page)
        at = AppTest.from_file(page_path, default_timeout=10)
        at.run()
        assert not at.exception, f"Page {page} raised an exception: {at.exception}"
