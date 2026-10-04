"""
Unit and integration tests for Fuel Predictor module.
Validates end-to-end flow:
- User Inputs validation
- Fuel Consumption Prediction (real ML vs Physics)
- CO2e and emissions calculations
- Cost calculation (Bunker + Carbon Tax)
- Carbon Intensity calculation (g CO2e / t-nm and CII rating proxy)
- Sensitivity: speed, cargo, distance, weather variation
- Multiple input combinations
- Multi-model comparisons (Quantum-Inspired Predictor, Polynomial Ridge, Gradient Boosting)
"""

import pytest
import pickle
from pathlib import Path
from src.prediction.fuel_model import FuelModel
from src.models.physics import load_config, calculate_leg_fuel_conventional
from api.index import predict_fuel, load_pkl


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def prediction_data():
    data = load_pkl("saved_prediction_results.pkl")
    assert data is not None, "saved_prediction_results.pkl must exist and be loadable"
    return data


def test_fuel_model_initialization_and_models(config, prediction_data):
    """Test that all 3 trained ML models initialize and predict without error."""
    trained_models = prediction_data.get("trained_models", {})
    assert len(trained_models) >= 3
    feature_names = prediction_data.get("feature_names")

    for model_name, model_obj in trained_models.items():
        fm = FuelModel(
            config=config,
            trained_predictor=model_obj,
            feature_names=feature_names,
            model_name=model_name,
        )
        # Test physics mode
        p_val = fm.predict(
            vessel_type="handymax_feeder",
            speed_knots=14.0,
            cargo_load_tonnes=16000.0,
            distance_nm=890.0,
            weather_severity=0.3,
            mode="physics",
        )
        assert p_val > 0.0

        # Test ML mode
        ml_val = fm.predict(
            vessel_type="handymax_feeder",
            speed_knots=14.0,
            cargo_load_tonnes=16000.0,
            distance_nm=890.0,
            weather_severity=0.3,
            mode="ml",
        )
        assert ml_val > 0.0
        # Check that ML value is plausible (within 30% of physics baseline)
        assert abs(ml_val - p_val) / p_val < 0.30


def test_predict_fuel_api_end_to_end():
    """Test that predict_fuel API function executes complete end-to-end calculations."""
    res = predict_fuel(
        vessel="handymax_feeder",
        speed=14.0,
        load_factor=80.0,
        weather=0.3,
        distance=890.0,
        fuel_type="HFO",
        fuel_price=550.0,
        carbon_tax=80.0,
        model_choice="Quantum-Inspired Predictor",
        mode="both",
    )

    assert res["status"] == "success"
    # Predictions
    assert res["prediction"]["fuel_tonnes"] > 0
    assert res["prediction"]["ml_prediction_tonnes"] > 0
    assert res["prediction"]["physics_estimate_tonnes"] > 0
    assert res["prediction"]["is_ml"] is True
    assert "Quantum-Inspired" in res["prediction"]["model_used"]

    # Economics
    assert res["economics"]["fuel_cost_usd"] > 0
    assert res["economics"]["carbon_tax_usd"] > 0
    assert res["economics"]["total_cost_usd"] == pytest.approx(
        res["economics"]["fuel_cost_usd"] + res["economics"]["carbon_tax_usd"], rel=1e-3
    )

    # Emissions & CII
    assert res["emissions"]["total_co2e_tonnes"] > 0
    assert res["emissions"]["carbon_intensity_g_tnm"] > 0
    assert res["emissions"]["carbon_intensity_rating"]["grade"] in ["A", "B", "C", "D", "E"]

    # Model Validation metrics exposed
    assert res["model_validation"]["mae"] is not None
    assert res["model_validation"]["rmse"] is not None
    assert res["model_validation"]["r2"] is not None
    assert len(res["speed_sweep"]) > 5


def test_sensitivity_speed_cargo_distance():
    """Verify that changing speed, cargo, and distance strictly affects the prediction as expected by physics/ML."""
    base = predict_fuel(
        vessel="handymax_feeder",
        speed=14.0,
        load_factor=80.0,
        weather=0.2,
        distance=1000.0,
        fuel_type="HFO",
    )
    base_fuel = base["prediction"]["ml_prediction_tonnes"]

    # 1. Higher speed must increase fuel consumption (cubic law)
    higher_speed = predict_fuel(
        vessel="handymax_feeder",
        speed=16.0,
        load_factor=80.0,
        weather=0.2,
        distance=1000.0,
        fuel_type="HFO",
    )
    assert higher_speed["prediction"]["ml_prediction_tonnes"] > base_fuel

    # 2. Longer distance must increase fuel consumption
    longer_dist = predict_fuel(
        vessel="handymax_feeder",
        speed=14.0,
        load_factor=80.0,
        weather=0.2,
        distance=1500.0,
        fuel_type="HFO",
    )
    assert longer_dist["prediction"]["ml_prediction_tonnes"] > base_fuel

    # 3. Higher cargo must increase fuel consumption
    higher_cargo = predict_fuel(
        vessel="handymax_feeder",
        speed=14.0,
        load_factor=95.0,
        weather=0.2,
        distance=1000.0,
        fuel_type="HFO",
    )
    assert higher_cargo["prediction"]["ml_prediction_tonnes"] > base_fuel


def test_three_distinct_input_combinations():
    """Test 3 distinct real-world voyage operational combinations."""
    combos = [
        # Combo 1: Short feeder transit, low speed, calm weather
        {"vessel": "small_feeder", "speed": 11.5, "load_factor": 60.0, "weather": 0.1, "distance": 350.0, "fuel_type": "MGO"},
        # Combo 2: Regional mainline feeder, medium speed, moderate weather, green fuel
        {"vessel": "handymax_feeder", "speed": 14.5, "load_factor": 85.0, "weather": 0.35, "distance": 1250.0, "fuel_type": "Methanol"},
        # Combo 3: Trunk panamax corridor, high speed, severe sea state
        {"vessel": "panamax_feeder", "speed": 18.0, "load_factor": 95.0, "weather": 0.65, "distance": 3200.0, "fuel_type": "LNG"},
    ]

    for c in combos:
        res = predict_fuel(**c)
        assert res["status"] == "success"
        assert res["prediction"]["fuel_tonnes"] > 0
        assert res["emissions"]["total_co2e_tonnes"] > 0
        assert res["economics"]["total_cost_usd"] > 0
        assert res["prediction"]["leg_days"] > 0
        assert res["prediction"]["difference_pct"] is not None
