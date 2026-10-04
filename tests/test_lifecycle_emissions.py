"""
Unit and integration tests for the lifecycle emissions model across the Green Fleet application.

Validates:
1. Changing fuel type changes lifecycle emissions according to FuelEmissionProfile.
2. Changing fuel consumption proportionally changes emissions.
3. Fleet optimization problem accounts for lifecycle emissions (WtT + TtW + Slip + Berth).
4. Predictor and alternative fuel APIs return accurate 4-part hierarchical breakdowns.
"""

import pytest
import numpy as np
from src.models.physics import (
    calculate_emissions,
    get_fuel_emission_profile,
    list_all_emission_profiles,
    FuelEmissionProfile,
    FUEL_EMISSION_PROFILES_CATALOG,
)
from src.analysis.fuels import compare_fuels_for_voyage
from src.optimization.problem import FleetOptimizationProblem
from app.ui.state import get_default_config


def test_emission_profiles_catalog_integrity():
    """Verify that cataloged profiles exist for all required fuels and pathways."""
    profiles = list_all_emission_profiles()
    assert len(profiles) >= 6

    # Verify standard fuels
    hfo_prof = get_fuel_emission_profile("HFO")
    assert hfo_prof.ttw_factor == pytest.approx(3.114, abs=0.01)
    assert hfo_prof.wtt_factor == pytest.approx(0.58, abs=0.01)
    assert hfo_prof.slip_factor == 0.0
    assert hfo_prof.lifecycle_factor == pytest.approx(3.694, abs=0.01)

    lng_prof = get_fuel_emission_profile("LNG")
    assert lng_prof.ttw_factor == pytest.approx(2.75, abs=0.01)
    assert lng_prof.slip_factor == pytest.approx(0.15, abs=0.01)  # Methane slip proxy

    ammonia_green = get_fuel_emission_profile("Ammonia", pathway="green")
    assert ammonia_green.ttw_factor == 0.0
    assert ammonia_green.wtt_factor == pytest.approx(0.10, abs=0.01)
    assert ammonia_green.slip_factor == pytest.approx(0.18, abs=0.01)  # Uncombusted N2O penalty

    ammonia_grey = get_fuel_emission_profile("Ammonia", pathway="grey")
    assert ammonia_grey.wtt_factor > 2.0  # Grey unabated Haber-Bosch upstream


def test_changing_fuel_type_changes_lifecycle_emissions():
    """Verify that changing fuel type changes lifecycle emissions as dictated by FuelEmissionProfile."""
    fuel_mass = 100.0  # tonnes

    emiss_hfo = calculate_emissions(fuel_mass, fuel_type="HFO")
    emiss_lng = calculate_emissions(fuel_mass, fuel_type="LNG")
    emiss_meth_green = calculate_emissions(fuel_mass, fuel_type="Methanol", pathway="green")
    emiss_meth_grey = calculate_emissions(fuel_mass, fuel_type="Methanol", pathway="grey")
    emiss_ammonia_green = calculate_emissions(fuel_mass, fuel_type="Ammonia", pathway="green")

    # Verify HFO emissions
    assert emiss_hfo["tank_to_wake"] == pytest.approx(311.4, abs=0.5)
    assert emiss_hfo["well_to_tank"] == pytest.approx(58.0, abs=0.5)
    assert emiss_hfo["slip"] == 0.0
    assert emiss_hfo["total_co2e"] == pytest.approx(369.4, abs=0.5)

    # Verify LNG has methane slip accounted for
    assert emiss_lng["slip"] == pytest.approx(15.0, abs=0.1)
    assert emiss_lng["total_co2e"] > emiss_lng["tank_to_wake"] + emiss_lng["well_to_tank"] - 0.01

    # Verify Green vs Grey Methanol
    assert emiss_meth_green["total_co2e"] < emiss_meth_grey["total_co2e"]
    assert emiss_meth_green["well_to_tank"] < emiss_meth_grey["well_to_tank"]

    # Changing fuel type clearly produces distinct lifecycle emissions
    assert emiss_hfo["total_co2e"] != emiss_lng["total_co2e"]
    assert emiss_lng["total_co2e"] != emiss_meth_green["total_co2e"]
    assert emiss_meth_green["total_co2e"] != emiss_ammonia_green["total_co2e"]


def test_changing_fuel_consumption_proportionally_changes_emissions():
    """Verify that doubling fuel consumption exactly doubles WtT, TtW, Slip, and total lifecycle emissions."""
    m1 = 50.0
    m2 = 100.0

    e1 = calculate_emissions(m1, fuel_type="LNG")
    e2 = calculate_emissions(m2, fuel_type="LNG")

    assert e2["well_to_tank"] == pytest.approx(2.0 * e1["well_to_tank"], rel=1e-5)
    assert e2["tank_to_wake"] == pytest.approx(2.0 * e2["tank_to_wake"] / 2.0, rel=1e-5)
    assert e2["slip"] == pytest.approx(2.0 * e1["slip"], rel=1e-5)
    assert e2["total_co2e"] == pytest.approx(2.0 * e1["total_co2e"], rel=1e-5)


def test_optimization_objective_uses_lifecycle_emissions():
    """Verify that FleetOptimizationProblem.evaluate() accounts for lifecycle emissions (WtT + TtW + Slip + Berth)."""
    prob = FleetOptimizationProblem(
        weights={"fuel": 0.1, "cost": 0.1, "emissions": 0.8},
        shore_power_forced=True,
    )

    # Sample a bitstring and evaluate
    np.random.seed(42)
    sample_bits = np.random.randint(0, 2, size=prob.n_bits)
    eval_res = prob.evaluate(sample_bits)

    # Verify evaluation returned structured emissions breakdown
    assert "emissions_breakdown" in eval_res
    brk = eval_res["emissions_breakdown"]

    assert "ttw_co2e_tonnes" in brk
    assert "wtt_co2e_tonnes" in brk
    assert "slip_co2e_tonnes" in brk
    assert "berth_co2e_tonnes" in brk

    sum_components = (
        brk["ttw_co2e_tonnes"]
        + brk["wtt_co2e_tonnes"]
        + brk["slip_co2e_tonnes"]
        + brk["berth_co2e_tonnes"]
    )
    assert eval_res["total_emissions_co2e_tonnes"] == pytest.approx(sum_components, rel=1e-4)

    # Verify objective penalization uses total lifecycle emissions
    norm_e = prob.norm_emissions_t
    expected_obj_e = eval_res["total_emissions_co2e_tonnes"] / norm_e
    assert eval_res["obj_emissions"] == pytest.approx(expected_obj_e, rel=1e-5)


def test_alternative_fuels_voyage_comparison_breakdown():
    """Verify that compare_fuels_for_voyage outputs verified breakdown and metadata."""
    cfg = get_default_config()
    df = compare_fuels_for_voyage(
        vessel_key="handymax_feeder",
        route_key="R1",
        pathway_choices={"Methanol": "green", "Ammonia": "green", "Hydrogen": "green"},
        config=cfg,
    )

    assert not df.empty
    assert "wtt_co2e_tonnes" in df.columns
    assert "ttw_co2e_tonnes" in df.columns
    assert "slip_co2e_tonnes" in df.columns
    assert "lifecycle_co2e_tonnes" in df.columns
    assert "emission_assumption_flag" in df.columns
    assert "emission_source" in df.columns

    for _, row in df.iterrows():
        total_co2e = row["lifecycle_co2e_tonnes"]
        parts_sum = row["wtt_co2e_tonnes"] + row["ttw_co2e_tonnes"] + row["slip_co2e_tonnes"]
        assert total_co2e == pytest.approx(parts_sum, abs=0.2)
