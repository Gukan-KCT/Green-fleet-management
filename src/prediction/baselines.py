"""
Conventional baseline regression models for fuel consumption prediction.
"""

from __future__ import annotations
from typing import Dict, Any
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor


def build_polynomial_regression(degree: int = 2, alpha: float = 1.0) -> Pipeline:
    """
    Polynomial Ridge Regression baseline with standard scaling.
    """
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
            ("regressor", Ridge(alpha=alpha, random_state=42)),
        ]
    )


def build_gradient_boosting(
    n_estimators: int = 100,
    learning_rate: float = 0.10,
    max_depth: int = 3,
    random_state: int = 42,
) -> GradientBoostingRegressor:
    """
    Default Gradient Boosting Regressor baseline.
    """
    return GradientBoostingRegressor(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        random_state=random_state,
    )


def build_random_forest(
    n_estimators: int = 100,
    max_depth: int = 8,
    random_state: int = 42,
) -> RandomForestRegressor:
    """
    Random Forest Regressor baseline.
    """
    return RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        n_jobs=-1,
        random_state=random_state,
    )
