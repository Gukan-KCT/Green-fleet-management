"""
Unit tests for Shore Power / Onshore Power Supply (OPS / Cold Ironing) module:
1. Port with OPS (Mumbai, Kochi) calculates grid energy, tariff cost, emissions, and avoids MGO fuel.
2. Port without OPS (Tuticorin) correctly falls back to onboard auxiliary engine (MGO) and rejects OPS connection.
3. Comparative tradeoff calculations: Without OPS vs With OPS, Fuel Saved, Cost Difference, CO2e Avoided, % Reduction.
4. Optimizer integration: UseShorePower[p,v] ∈ {0,1} decision variable changes optimizer output when OPS is enabled vs disabled.
5. Feasibility constraint enforcement: Impossible OPS selections (e.g. at Tuticorin or with incompatible vessel) are rejected/penalized.
"""

import pytest
import numpy as np
from src.models.physics import load_config, calculate_berth_energy_and_emissions
from src.analysis.shore_power import calculate_ops_tradeoff, analyze_shore_power_fleet
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.planner import optimize_fleet_plan


@pytest.fixture
def config():
    return load_config()


def test_port_with_ops(config):
    """
    1. Test a port with OPS (Mumbai).
    Vessel arrives at port -> Berthing duration -> Hotel energy demand -> Shore power availability ->
    Electricity consumption -> Shore power cost -> Avoided auxiliary engine fuel -> Avoided emissions.
    """
    port_mumbai = config["ports"]["mumbai"]
    aux_kw = 650.0  # Handymax feeder
    berth_hours = 24.0
    eff = 0.95

    # Run calculate_berth_energy_and_emissions
    res = calculate_berth_energy_and_emissions(
        aux_kw=aux_kw,
        berth_hours=berth_hours,
        use_shore_power=True,
        port_cfg=port_mumbai,
        config=config,
        connection_efficiency=eff,
    )

    assert res["ops_feasible"] is True
    assert res["ops_active"] is True
    assert res["power_source"] == "shore_grid"
    assert res["fuel_tonnes"] == 0.0  # Zero onboard fuel while connected to grid

    # Verify electricity consumption: E_grid = (aux_kw * berth_hours) / eff
    expected_kwh = (aux_kw * berth_hours) / eff
    expected_mwh = expected_kwh / 1000.0
    assert np.isclose(res["mwh_consumed"], expected_mwh, rtol=1e-3)

    # Verify electricity cost: Cost_grid = MWh * Tariff ($120/MWh)
    expected_cost = expected_mwh * float(port_mumbai["electricity_price_usd_per_mwh"])
    assert np.isclose(res["cost_usd"], expected_cost, rtol=1e-3)

    # Verify grid emissions: MWh * Grid EF (0.71 t CO2e/MWh)
    expected_emiss = expected_mwh * float(port_mumbai["grid_ef_tonnes_per_mwh"])
    assert np.isclose(res["emissions_co2e"], expected_emiss, rtol=1e-3)

    # Verify avoided fuel and avoided emissions
    without_ops = res["without_ops"]
    assert without_ops["fuel_tonnes"] > 0.0
    assert res["fuel_saved_tonnes"] == without_ops["fuel_tonnes"]
    assert res["co2e_avoided_tonnes"] > 0.0
    assert res["percentage_reduction"] > 0.0


def test_port_without_ops(config):
    """
    2. Test a port without OPS (Tuticorin).
    Shore power is unavailable. System must reject OPS connection, fall back to onboard
    auxiliary engine burning MGO, and record zero avoided fuel.
    """
    port_tuticorin = config["ports"]["tuticorin"]
    aux_kw = 650.0
    berth_hours = 18.0

    res = calculate_berth_energy_and_emissions(
        aux_kw=aux_kw,
        berth_hours=berth_hours,
        use_shore_power=True,  # Vessel attempts to use shore power
        port_cfg=port_tuticorin,
        config=config,
    )

    assert res["ops_feasible"] is False
    assert res["ops_active"] is False
    assert res["power_source"] == "onboard_aux_gen"
    assert res["fuel_tonnes"] > 0.0  # Must run generator
    assert res["fuel_saved_tonnes"] == 0.0
    assert res["co2e_avoided_tonnes"] == 0.0
    assert res["percentage_reduction"] == 0.0


def test_compare_results_tradeoff(config):
    """
    3. Compare single-port tradeoff results between OPS Ready port and Non-OPS port.
    """
    tradeoff_mumbai = calculate_ops_tradeoff(
        port_id="mumbai",
        vessel_type="handymax_feeder",
        berth_hours=24.0,
        config=config,
    )
    tradeoff_tuticorin = calculate_ops_tradeoff(
        port_id="tuticorin",
        vessel_type="handymax_feeder",
        berth_hours=24.0,
        config=config,
    )

    # Mumbai (with OPS)
    assert tradeoff_mumbai["ops_feasible"] is True
    assert tradeoff_mumbai["tradeoff"]["fuel_saved_tonnes"] > 0.0
    assert tradeoff_mumbai["tradeoff"]["percentage_reduction"] > 5.0  # Positive reduction vs MGO generator
    assert tradeoff_mumbai["rejection_reason"] is None

    # Tuticorin (without OPS)
    assert tradeoff_tuticorin["ops_feasible"] is False
    assert tradeoff_tuticorin["tradeoff"]["fuel_saved_tonnes"] == 0.0
    assert tradeoff_tuticorin["tradeoff"]["percentage_reduction"] == 0.0
    assert "lacks high-voltage shore connection" in tradeoff_tuticorin["rejection_reason"]


def test_optimizer_output_changes_when_ops_enabled(config):
    """
    4. Verify optimizer output changes when shore power is enabled vs disabled.
    Plan A (No shore power) vs Plan B (With shore power enabled).
    """
    # Plan A: Shore power forced False
    prob_no_ops = FleetOptimizationProblem(shore_power_forced=False, config=config)
    # Plan B: Shore power forced True
    prob_with_ops = FleetOptimizationProblem(shore_power_forced=True, config=config)

    # Evaluate the exact same vessel deployment on both problems
    test_bits = np.ones(prob_no_ops.n_bits, dtype=int)
    eval_no_ops = prob_no_ops.evaluate(test_bits)
    eval_with_ops = prob_with_ops.evaluate(test_bits)

    # Plan B with shore power must achieve lower lifecycle emissions than Plan A
    assert eval_with_ops["total_emissions_co2e_tonnes"] < eval_no_ops["total_emissions_co2e_tonnes"]

    # Plan B must record positive berth fuel saved
    assert eval_with_ops["shore_power_metrics"]["berth_fuel_saved_tonnes"] > 0.0
    assert eval_no_ops["shore_power_metrics"]["berth_fuel_saved_tonnes"] == 0.0

    # Plan B must consume electricity from port grids
    assert eval_with_ops["shore_power_metrics"]["berth_electricity_mwh"] > 0.0
    assert eval_no_ops["shore_power_metrics"]["berth_electricity_mwh"] == 0.0


def test_impossible_ops_selections_rejected(config):
    """
    5. Verify impossible OPS selections are rejected / penalized.
    - If a chromosome requests shore power on a port that does not support it (e.g. Tuticorin),
      repair_solution() must turn it to 0, and evaluate() must flag a constraint violation.
    - If berthing duration is below the minimum safe threshold (e.g. 1.0 hour < 2.0 hours),
      OPS connection is rejected.
    """
    prob = FleetOptimizationProblem(config=config)
    
    # Construct a bitstring where shore_power bit for Tuticorin is set to 1
    tuticorin_idx = prob.n_alloc_bits + prob.n_speed_bits + prob.port_keys.index("tuticorin")
    bad_bits = np.zeros(prob.n_bits, dtype=int)
    bad_bits[tuticorin_idx] = 1

    # Before repair, evaluate flags the impossible selection
    eval_bad = prob.evaluate(bad_bits)
    assert eval_bad["constraint_violations"]["shore_power"] > 0.0

    # repair_solution must automatically reset Tuticorin's shore power to 0
    repaired_bits = prob.repair_solution(bad_bits)
    allocs, speeds, sp_repaired = prob.decode_solution(repaired_bits)
    assert sp_repaired["tuticorin"] is False

    # Short berthing duration check:
    short_berth = calculate_ops_tradeoff(
        port_id="mumbai",
        berth_hours=1.0,  # Below min threshold 2.0h
        min_berth_hours=2.0,
        config=config,
    )
    assert short_berth["ops_feasible"] is False
    assert "below minimum safe connection threshold" in short_berth["rejection_reason"]
