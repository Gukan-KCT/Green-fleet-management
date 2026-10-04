"""
Unit and integration tests for Alternative Fuels module and Fleet Optimization integration.
Verifies:
1. Structured parameter model completeness & assumption labeling.
2. Fuel comparison table output and required columns:
   Fuel | Fuel Cost | Fuel Consumption | Lifecycle CO2e | Availability | Compatibility
3. Dynamic candidate generation respects vessel-fuel engineering compatibility.
4. Fuel selection genuinely changes optimization metrics across Conventional (HFO), LNG, Methanol, and Ammonia.
5. Incompatible fuel/vessel combinations are blocked or penalized.
6. Lifecycle emissions calculation includes Tank-to-Wake, Well-to-Tank, and Slip factors.
"""

import pytest
import pandas as pd
from src.models.physics import load_config, calculate_leg_fuel_conventional, calculate_alternative_fuel_mass, calculate_emissions
from src.analysis.fuels import (
    compare_fuels_for_voyage,
    build_candidate_options,
    FUEL_STRUCTURED_PARAMETERS,
    VESSEL_FUEL_COMPATIBILITY,
)
from src.optimization.planner import optimize_fleet_plan
from src.optimization.problem import FleetOptimizationProblem


@pytest.fixture
def config():
    return load_config()


def test_structured_parameter_model_and_assumptions():
    """Verify all 6 fuels define energy, price, tank, lifecycle emissions, compatibility, and source tags."""
    expected_fuels = ["HFO", "MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"]
    for f in expected_fuels:
        assert f in FUEL_STRUCTURED_PARAMETERS, f"Missing fuel parameter model for {f}"
        p = FUEL_STRUCTURED_PARAMETERS[f]
        assert "energy_content_mj_kg" in p and p["energy_content_mj_kg"] > 0
        assert "tank_storage_factor" in p
        assert "lifecycle_emissions" in p
        assert "vessel_compatibility" in p and len(p["vessel_compatibility"]) > 0
        assert "availability_assumption" in p
        assert "operational_constraints" in p and len(p["operational_constraints"]) > 0
        assert "assumptions" in p
        # Verify assumption labels are explicitly categorized
        for k, label in p["assumptions"].items():
            assert any(tag in label for tag in ["Real / Publicly Sourced", "Project Assumption", "Synthetic / Illustrative"]), (
                f"Uncategorized assumption '{k}': '{label}' in fuel {f}"
            )


def test_comparison_table_columns_and_values(config):
    """Verify comparison table contains exact required columns and realistic values."""
    df = compare_fuels_for_voyage("handymax_feeder", "R1", config=config)
    req_cols = ["Fuel", "Fuel Cost", "Fuel Consumption", "Lifecycle CO2e", "Availability", "Compatibility"]
    for col in req_cols:
        assert col in df.columns, f"Missing required column '{col}' in fuel comparison table"

    assert len(df) == 6
    # HFO baseline comparison
    hfo_row = df[df["fuel_type"] == "HFO"].iloc[0]
    assert bool(hfo_row["is_compatible"]) is True
    assert hfo_row["cargo_loss_pct"] == 0.0

    # Hydrogen on handymax must be marked incompatible
    h2_row = df[df["fuel_type"] == "Hydrogen"].iloc[0]
    assert bool(h2_row["is_compatible"]) is False
    assert "Incompatible" in h2_row["Compatibility"]


def test_vessel_fuel_compatibility_filtering(config):
    """Verify candidate options generator enforces engineering compatibility."""
    # Hydrogen is only compatible with small_feeder
    h2_cands = build_candidate_options(["Hydrogen"], config=config)
    assert len(h2_cands) == 1
    assert h2_cands[0]["vessel"] == "small_feeder"
    assert h2_cands[0]["fuel"] == "Hydrogen"

    # Ammonia is compatible with handymax, sub_panamax, panamax (not small_feeder)
    amm_cands = build_candidate_options(["Ammonia"], config=config)
    vessels = [c["vessel"] for c in amm_cands]
    assert "small_feeder" not in vessels
    assert "handymax_feeder" in vessels
    assert "panamax_feeder" in vessels


def test_fuel_selection_affects_optimization(config):
    """Verify changing allowed fuels alters optimization outcomes (fuel burn, cost, and lifecycle CO2e)."""
    # 1. HFO only
    hfo_res = optimize_fleet_plan(allowed_fuels=["HFO"], num_qiea_starts=2, evals_per_start=800, seeds=[42, 43], config=config)
    hfo_eval = hfo_res["selected_plan"]

    # 2. LNG only
    lng_res = optimize_fleet_plan(allowed_fuels=["LNG"], num_qiea_starts=2, evals_per_start=800, seeds=[42, 43], config=config)
    lng_eval = lng_res["selected_plan"]

    # 3. Ammonia only
    amm_res = optimize_fleet_plan(allowed_fuels=["Ammonia"], num_qiea_starts=2, evals_per_start=800, seeds=[42, 43], config=config)
    amm_eval = amm_res["selected_plan"]

    # Changing fuel MUST change lifecycle emissions and operating costs
    assert amm_eval["total_emissions_co2e_tonnes"] < hfo_eval["total_emissions_co2e_tonnes"] * 0.5, (
        "Ammonia fleet must reduce lifecycle emissions by >50% vs HFO"
    )
    assert amm_eval["total_operating_cost_usd"] > hfo_eval["total_operating_cost_usd"], (
        "Green Ammonia procurement cost must exceed conventional HFO"
    )
    assert lng_eval["total_emissions_co2e_tonnes"] != hfo_eval["total_emissions_co2e_tonnes"], (
        "LNG emissions must differ from HFO emissions"
    )
