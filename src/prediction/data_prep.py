"""
Data loading and preprocessing utilities for fuel consumption prediction.
"""

from __future__ import annotations
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


def load_synthetic_fuel_data(csv_path: str | Path = "data/synthetic_fuel.csv") -> pd.DataFrame:
    """
    Load synthetic fuel consumption data, skipping header comment lines.
    """
    path = Path(csv_path)
    if not path.is_file():
        candidate = Path(__file__).resolve().parents[2] / csv_path
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(f"Synthetic fuel data not found at: {csv_path}")

    # Read CSV skipping lines starting with '#'
    df = pd.read_csv(path, comment="#")
    return df


def prepare_features_and_target(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, List[str]]:
    """
    One-hot encode vessel_type and split into train and test sets.
    """
    # Features to encode
    feature_cols = [
        "speed_knots",
        "cargo_load_tonnes",
        "distance_nm",
        "weather_severity",
        "sea_state",
        "hull_condition",
    ]

    # One-hot encode vessel_type with fixed order for determinism
    vessel_dummies = pd.get_dummies(df["vessel_type"], prefix="vessel", dtype=float)

    X = pd.concat([vessel_dummies, df[feature_cols]], axis=1)
    y = df["fuel_consumed_tonnes"]

    feature_names = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    return X_train, X_test, y_train, y_test, feature_names
