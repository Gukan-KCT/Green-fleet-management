"""
Unit tests for mathematical physics, energy equivalence, emissions, and berth calculations.
"""

import pytest
import math
from src.models.physics import (
    load_config,
    calculate_leg_fuel_conventional,
    calculate_alternative_fuel_mass,
    calculate_fuel_energy_gj,
    calculate_emissions,
    calculate_usable_capacity_teu,
    calculate_berth_energy_and_emissions,
    calculate_schedule_reliability,
)


@pytest.fixture
def config():
    return load_config()


def test_speed_monotonicity(config):
    """Verify that daily fuel consumption strictly increases with speed (cubic law)."""
    vessel = config["vessel_types"]["handymax_feeder"]
    dist = 500.0
    load = 15000.0
    weather = 0.2

    fuel_12, _ = calculate_leg_fuel_conventional(vessel, 12.0, dist, load, weather)
    fuel_14, _ = calculate_leg_fuel_conventional(vessel, 14.0, dist, load, weather)
    fuel_16, _ = calculate_leg_fuel_conventional(vessel, 16.0, dist, load, weather)

    # Note: leg fuel = daily_fuel * (dist / 24V) = F_ref * (V/V_ref)^3 * (d / 24V) ~ V^2
    # So leg fuel must strictly increase with speed
    assert fuel_12 < fuel_14 < fuel_16


def test_load_monotonicity(config):
    """Verify that fuel consumption increases with cargo payload displacement."""
    vessel = config["vessel_types"]["handymax_feeder"]
    dist = 500.0
    speed = 14.0
    weather = 0.2

    fuel_empty, _ = calculate_leg_fuel_conventional(vessel, speed, dist, 2000.0, weather)
    fuel_half, _ = calculate_leg_fuel_conventional(vessel, speed, dist, 10000.0, weather)
    fuel_full, _ = calculate_leg_fuel_conventional(vessel, speed, dist, 20000.0, weather)

    assert fuel_empty < fuel_half < fuel_full


def test_weather_monotonicity(config):
    """Verify that adverse weather increases fuel consumption."""
    vessel = config["vessel_types"]["handymax_feeder"]
    dist = 500.0
    speed = 14.0
    load = 15000.0

    fuel_calm, _ = calculate_leg_fuel_conventional(vessel, speed, dist, load, 0.0)
    fuel_moderate, _ = calculate_leg_fuel_conventional(vessel, speed, dist, load, 0.4)
    fuel_rough, _ = calculate_leg_fuel_conventional(vessel, speed, dist, load, 0.8)

    assert fuel_calm < fuel_moderate < fuel_rough


def test_energy_equivalence(config):
    """Verify energy equivalence conversion across alternative fuels."""
    hfo_mass = 100.0  # 100 tonnes HFO
    fuels = ["MGO", "LNG", "Methanol", "Ammonia", "Hydrogen"]

    for f in fuels:
        alt_mass = calculate_alternative_fuel_mass(hfo_mass, f, config)
        assert alt_mass > 0.0

        # Hydrogen has very high LHV (120 MJ/kg vs 40 MJ/kg HFO), so mass must be much smaller
        if f == "Hydrogen":
            assert alt_mass < hfo_mass * 0.45
        # Methanol and ammonia have lower LHV (~20 MJ/kg), so mass must be larger
        if f in ["Methanol", "Ammonia"]:
            assert alt_mass > hfo_mass * 1.5


def test_emissions_arithmetic(config):
    """Verify Well-to-Wake total equals sum of TtW, WtT, and slip."""
    fuel_mass = 50.0
    emiss_hfo = calculate_emissions(fuel_mass, "HFO", config=config)
    assert math.isclose(
        emiss_hfo["total_co2e"],
        emiss_hfo["tank_to_wake"] + emiss_hfo["well_to_tank"] + emiss_hfo["slip"],
        rel_tol=1e-5,
    )

    # Green ammonia should have zero tailpipe emissions
    emiss_nh3 = calculate_emissions(fuel_mass, "Ammonia", pathway="green", config=config)
    assert emiss_nh3["tank_to_wake"] == 0.0
    assert emiss_nh3["total_co2e"] > 0.0  # slip + small wtt


def test_capacity_penalty(config):
    """Verify usable TEU decreases for bulky alternative fuels."""
    nom_teu = 1800.0
    teu_hfo = calculate_usable_capacity_teu(nom_teu, "HFO", config)
    teu_meth = calculate_usable_capacity_teu(nom_teu, "Methanol", config)
    teu_nh3 = calculate_usable_capacity_teu(nom_teu, "Ammonia", config)
    teu_h2 = calculate_usable_capacity_teu(nom_teu, "Hydrogen", config)

    assert teu_hfo == nom_teu
    assert teu_hfo > teu_meth > teu_nh3 > teu_h2


def test_berth_shore_power(config):
    """Verify cold ironing zeroes onboard generator fuel and utilizes port grid."""
    port_mumbai = config["ports"]["mumbai"]
    aux_kw = 650.0
    hours = 24.0

    # With shore power
    sp_on = calculate_berth_energy_and_emissions(aux_kw, hours, True, port_mumbai, config)
    assert sp_on["fuel_tonnes"] == 0.0
    assert sp_on["power_source"] == "shore_grid"
    assert sp_on["cost_usd"] > 0.0

    # Without shore power
    sp_off = calculate_berth_energy_and_emissions(aux_kw, hours, False, port_mumbai, config)
    assert sp_off["fuel_tonnes"] > 0.0
    assert sp_off["power_source"] == "onboard_aux_gen"
