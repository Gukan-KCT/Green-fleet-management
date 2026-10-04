"""
Unified FuelModel interface supporting both analytical physics and trained ML predictors.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

from src.models.physics import calculate_leg_fuel_conventional, load_config
from src.prediction.evaluator import evaluate_prediction_models


class FuelModel:
    """
    Unified fuel consumption predictor with toggleable backend modes:
    - 'physics': Analytical cubic speed and Admiralty displacement physics.
      Deterministic, robust to extreme domain extrapolation.
    - 'ml': Real trained ML regressor (Quantum-Inspired Predictor, Polynomial Ridge, or Gradient Boosting).
      Trained on empirical synthetic hydrodynamic voyage dataset.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        trained_predictor: Optional[Any] = None,
        feature_names: Optional[list] = None,
        model_name: str = "Quantum-Inspired Predictor",
    ):
        self.config = config or load_config()
        self.trained_predictor = trained_predictor
        self.feature_names = feature_names or [
            "vessel_handymax_feeder",
            "vessel_panamax_feeder",
            "vessel_small_feeder",
            "vessel_sub_panamax_feeder",
            "speed_knots",
            "cargo_load_tonnes",
            "distance_nm",
            "weather_severity",
            "sea_state",
            "hull_condition",
        ]
        self.model_name = model_name

    def predict(
        self,
        vessel_type: str,
        speed_knots: float,
        cargo_load_tonnes: float,
        distance_nm: float,
        weather_severity: float,
        sea_state: Optional[int] = None,
        hull_condition: float = 1.0,
        mode: str = "physics",
    ) -> float:
        """
        Predict fuel consumption in tonnes for a given voyage leg.

        Args:
            vessel_type: Vessel key (e.g. 'handymax_feeder', 'panamax_feeder').
            speed_knots: Speed through water in knots.
            cargo_load_tonnes: Actual cargo mass in tonnes.
            distance_nm: Leg distance in nautical miles.
            weather_severity: Weather severity index in [0, 1].
            sea_state: Optional Douglas sea state scale (0-8).
            hull_condition: Hull biofouling/roughness factor (~1.0).
            mode: 'physics' or 'ml'.

        Returns:
            Estimated fuel consumption in tonnes.
        """
        if mode == "physics" or self.trained_predictor is None:
            vessel_cfg = self.config["vessel_types"][vessel_type]
            k_w = float(self.config["general"].get("weather_penalty_k_w", 0.35))
            leg_fuel, _ = calculate_leg_fuel_conventional(
                vessel_cfg=vessel_cfg,
                speed_knots=speed_knots,
                distance_nm=distance_nm,
                cargo_load_tonnes=cargo_load_tonnes,
                weather_severity=weather_severity,
                k_w=k_w,
            )
            return float(leg_fuel)

        # ML mode: construct feature DataFrame with strictly aligned feature columns
        if sea_state is None:
            sea_state = int(np.clip(round(weather_severity * 8.0), 0, 8))

        row_dict: Dict[str, float] = {
            "vessel_handymax_feeder": 1.0 if vessel_type == "handymax_feeder" else 0.0,
            "vessel_panamax_feeder": 1.0 if vessel_type == "panamax_feeder" else 0.0,
            "vessel_small_feeder": 1.0 if vessel_type == "small_feeder" else 0.0,
            "vessel_sub_panamax_feeder": 1.0 if vessel_type == "sub_panamax_feeder" else 0.0,
            "speed_knots": float(speed_knots),
            "cargo_load_tonnes": float(cargo_load_tonnes),
            "distance_nm": float(distance_nm),
            "weather_severity": float(weather_severity),
            "sea_state": float(sea_state),
            "hull_condition": float(hull_condition),
        }

        # Order columns strictly matching feature_names or model's expected features
        target_features = self.feature_names
        if hasattr(self.trained_predictor, "feature_names_in_"):
            target_features = list(self.trained_predictor.feature_names_in_)
        elif hasattr(self.trained_predictor, "selected_features_"):
            target_features = list(self.trained_predictor.selected_features_)

        X_df = pd.DataFrame([row_dict])
        # Ensure any missing columns exist with 0.0
        for col in target_features:
            if col not in X_df.columns:
                X_df[col] = 0.0
        X_df = X_df[target_features]

        pred = self.trained_predictor.predict(X_df)[0]
        return float(max(0.1, pred))

