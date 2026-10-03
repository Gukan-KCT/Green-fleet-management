"""
Unit tests for operational and regulatory constraints in fleet deployment.
Includes frequency, reliability, speed limits, bunkering, and supply cap tests.
"""

import pytest
import numpy as np
from src.optimization.problem import FleetOptimizationProblem


@pytest.fixture
def problem():
    return FleetOptimizationProblem()


def test_demand_infeasible(problem):
    """An all-zero assignment bitstring must flag severe demand violations."""
    zero_bits = np.zeros(problem.n_bits, dtype=int)
    eval_res = problem.evaluate(zero_bits)

    assert not eval_res["is_feasible"]
    assert eval_res["constraint_violations"]["demand"] > 0.0
    assert eval_res["total_cargo_delivered_teu"] == 0.0


def test_availability_infeasible(problem):
    """Allocating more vessels than fleet availability must trigger violation."""
    bits = np.zeros(problem.n_bits, dtype=int)
    n_opts = len(problem.options)
    n_routes = len(problem.route_keys)

    # Option 0 is small_feeder (availability = 8).
    # Assign max (3 vessels) to all 5 routes = 15 vessels > 8
    idx = 0
    for o in range(n_opts):
        for r in range(n_routes):
            if o == 0:
                bits[idx] = 1
                bits[idx + 1] = 1  # 3 vessels
            idx += 2

    eval_res = problem.evaluate(bits)
    assert not eval_res["is_feasible"]
    assert eval_res["constraint_violations"]["vessel_availability"] > 0.0


def test_bunkering_constraint(problem):
    """Assigning Ammonia or Hydrogen to a route whose ports do not support it must flag violation."""
    # Tuticorin (origin of R4) only supports HFO and MGO.
    # Colombo supports Ammonia, but NOT Hydrogen.
    # Route R4 (Tuticorin - Colombo) does not support Hydrogen.
    opts_with_h2 = list(problem.options) + [
        {"vessel": "small_feeder", "fuel": "Hydrogen", "pathway": "green"}
    ]
    prob_h2 = FleetOptimizationProblem(candidate_options=opts_with_h2)

    h2_opt_idx = len(opts_with_h2) - 1
    r4_idx = prob_h2.route_keys.index("R4")

    bits = np.zeros(prob_h2.n_bits, dtype=int)
    # Set 2 vessels on (h2_opt_idx, r4_idx)
    idx = 2 * (h2_opt_idx * len(prob_h2.route_keys) + r4_idx)
    bits[idx] = 1
    bits[idx + 1] = 0  # 2 vessels

    eval_res = prob_h2.evaluate(bits)
    assert eval_res["constraint_violations"]["fuel_bunkering"] > 0.0


def test_carbon_intensity_cap_infeasible(problem):
    """Setting an extremely stringent carbon intensity cap flags compliance violation."""
    strict_prob = FleetOptimizationProblem(carbon_intensity_cap=5.0)  # Unattainable 5 g/t-nm cap
    bits = np.zeros(strict_prob.n_bits, dtype=int)
    idx = 0
    for o in range(len(strict_prob.options)):
        for r in range(len(strict_prob.route_keys)):
            if o == 2:  # Handymax HFO
                bits[idx] = 0
                bits[idx + 1] = 1  # 1 vessel
            idx += 2

    eval_res = strict_prob.evaluate(bits)
    assert eval_res["constraint_violations"]["carbon_intensity"] > 0.0


def test_frequency_constraint(problem):
    """If sailings per week is below min_sailings_per_week, frequency violation must be flagged."""
    bits = np.zeros(problem.n_bits, dtype=int)
    # Assign only 1 small vessel to R5 (Colombo - Singapore, distance 1580 nm, min_freq = 1.0)
    # Round trip is ~3160 nm, at 10.5 kn transit is ~300h -> only ~28 trips/yr -> 0.54 sailings/wk < 1.0
    r5_idx = problem.route_keys.index("R5")
    idx = 2 * (0 * len(problem.route_keys) + r5_idx)
    bits[idx] = 0
    bits[idx + 1] = 1  # 1 vessel

    eval_res = problem.evaluate(bits)
    assert eval_res["constraint_violations"]["frequency"] > 0.0


def test_reliability_constraint(problem):
    """Setting a demanding reliability threshold flags schedule reliability violations."""
    prob_strict_rel = FleetOptimizationProblem(carbon_intensity_cap=100.0)
    prob_strict_rel.reliability_threshold = 0.95

    bits = np.zeros(prob_strict_rel.n_bits, dtype=int)
    idx = 0
    for o in range(len(prob_strict_rel.options)):
        for r in range(len(prob_strict_rel.route_keys)):
            if o == 2:  # Handymax
                bits[idx] = 0
                bits[idx + 1] = 1
            idx += 2
    # Set speed to maximum (level 7 = 17.5 kn, near Handymax v_max of 18.0 kn)
    for r in range(len(prob_strict_rel.route_keys)):
        bits[idx] = 1
        bits[idx + 1] = 1
        bits[idx + 2] = 1
        idx += 3

    eval_res = prob_strict_rel.evaluate(bits)
    assert eval_res["constraint_violations"]["reliability"] > 0.0


def test_speed_limits(problem):
    """Decoded cruising speeds must always respect v_min and speed cap limits."""
    prob_capped = FleetOptimizationProblem(speed_cap_delta=-3.0)
    bits = np.ones(prob_capped.n_bits, dtype=int)
    allocs, speeds, sp = prob_capped.decode_solution(bits)

    for r_k, spd in speeds.items():
        r_cfg = prob_capped.routes[r_k]
        cap = float(r_cfg["speed_cap_knots"]) - 3.0
        assert spd <= cap + 1e-4


def test_supply_cap_violation(problem):
    """Oversupplying capacity beyond supply_cap_ratio must flag a supply_cap violation."""
    prob_capped = FleetOptimizationProblem(supply_cap_ratio=1.2)  # Cap at 120% of demand

    bits = np.zeros(prob_capped.n_bits, dtype=int)
    # Assign 3 Handymax vessels to R4 (Tuticorin - Colombo, demand 65,000 TEU)
    # Handymax capacity: 3 vessels * ~60 trips * 1800 TEU = ~320,000 TEU >> 65,000 * 1.2
    r4_idx = prob_capped.route_keys.index("R4")
    idx = 2 * (2 * len(prob_capped.route_keys) + r4_idx)
    bits[idx] = 1
    bits[idx + 1] = 1  # 3 vessels

    eval_res = prob_capped.evaluate(bits)
    assert eval_res["constraint_violations"]["supply_cap"] > 0.0
