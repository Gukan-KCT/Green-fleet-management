"""
Benchmark and evaluation module for fuel consumption prediction models.
Includes paired Wilcoxon signed-rank significance testing across cross-validation folds.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import root_mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import RepeatedKFold, KFold
from sklearn.ensemble import GradientBoostingRegressor

from src.prediction.data_prep import load_synthetic_fuel_data, prepare_features_and_target
from src.prediction.baselines import build_polynomial_regression, build_gradient_boosting
from src.prediction.q_predictor import QuantumInspiredPredictor


def evaluate_prediction_models(
    csv_path: str = "data/synthetic_fuel.csv",
    cv_folds: int = 5,
    qiea_pop_size: int = 10,
    qiea_generations: int = 12,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Train and rigorously evaluate:
    1. Polynomial Ridge Regression (degree 2)
    2. Standard Gradient Boosting Regressor
    3. Quantum-Inspired Predictor (QIEA feature & hyperparameter optimization)

    Returns test metrics (RMSE, MAE, R^2), paired Wilcoxon signed-rank tests,
    convergence curves, and test predictions for plotting.
    """
    df = load_synthetic_fuel_data(csv_path)
    X_train, X_test, y_train, y_test, feature_names = prepare_features_and_target(
        df, test_size=0.2, random_state=random_seed
    )

    models = {
        "Polynomial Ridge": build_polynomial_regression(degree=2, alpha=1.0),
        "Gradient Boosting (Default)": build_gradient_boosting(n_estimators=80, learning_rate=0.1, random_state=random_seed),
        "Quantum-Inspired Predictor": QuantumInspiredPredictor(
            population_size=qiea_pop_size,
            generations=qiea_generations,
            rotation_angle=0.06,
            mutation_rate=0.03,
            cv_folds=3,
            random_state=random_seed,
        ),
    }

    results = {}
    test_predictions = {"actual": y_test.values}

    # 1. Fit models on training set and evaluate on test set
    for name, model in models.items():
        if name == "Quantum-Inspired Predictor":
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
        else:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)

        test_predictions[name] = preds

        rmse = float(root_mean_squared_error(y_test, preds))
        mae = float(mean_absolute_error(y_test, preds))
        r2 = float(r2_score(y_test, preds))

        results[name] = {
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "r2": round(r2, 4),
            "model_obj": model,
        }

    # 2. Paired Cross-Validation for Wilcoxon Signed-Rank Test (Repeated 10-fold CV)
    rkf = RepeatedKFold(n_splits=10, n_repeats=2, random_state=random_seed)
    fold_rmses: Dict[str, list] = {name: [] for name in models.keys()}

    for train_idx, val_idx in rkf.split(X_train):
        X_f_tr, X_f_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_f_tr, y_f_val = y_train.iloc[train_idx], y_train.iloc[val_idx]

        # Polynomial Ridge fold
        poly_m = build_polynomial_regression(degree=2, alpha=1.0)
        poly_m.fit(X_f_tr, y_f_tr)
        p_preds = poly_m.predict(X_f_val)
        fold_rmses["Polynomial Ridge"].append(root_mean_squared_error(y_f_val, p_preds))

        # Gradient Boosting fold
        gb_m = build_gradient_boosting(n_estimators=80, learning_rate=0.1, random_state=random_seed)
        gb_m.fit(X_f_tr, y_f_tr)
        gb_preds = gb_m.predict(X_f_val)
        fold_rmses["Gradient Boosting (Default)"].append(root_mean_squared_error(y_f_val, gb_preds))

        # Q-Predictor fold (using its tuned hyperparameters and features)
        q_m = models["Quantum-Inspired Predictor"]
        sel_feats = q_m.selected_features_
        q_reg = GradientBoostingRegressor(**q_m.best_params_)
        q_reg.fit(X_f_tr[sel_feats], y_f_tr)
        q_preds = q_reg.predict(X_f_val[sel_feats])
        fold_rmses["Quantum-Inspired Predictor"].append(root_mean_squared_error(y_f_val, q_preds))

    # Compute Wilcoxon tests (two-sided, reporting difference direction, no bare except)
    q_folds = np.array(fold_rmses["Quantum-Inspired Predictor"])
    significance_tests = {}

    for baseline_name in ["Polynomial Ridge", "Gradient Boosting (Default)"]:
        base_folds = np.array(fold_rmses[baseline_name])
        diff = base_folds - q_folds  # Positive means Q-predictor has lower RMSE (better)

        mean_rmse_base = float(np.mean(base_folds))
        mean_rmse_q = float(np.mean(q_folds))

        # Explicit handling of zero differences instead of bare except
        if np.all(np.isclose(diff, 0.0)):
            stat, p_val = 0.0, 1.0
        else:
            w_res = stats.wilcoxon(diff, alternative="two-sided", zero_method="wilcox")
            stat, p_val = float(w_res.statistic), float(w_res.pvalue)

        is_significant = bool(p_val < 0.05)

        if mean_rmse_q < mean_rmse_base:
            direction = "QIEA lower error"
            if is_significant:
                interpretation = (
                    f"Statistically significant difference (p = {p_val:.4f} < 0.05, two-sided): "
                    f"QIEA-tuned model achieved lower mean RMSE ({mean_rmse_q:.4f} vs {mean_rmse_base:.4f} tonnes)."
                )
            else:
                interpretation = (
                    f"No statistically significant difference (p = {p_val:.4f} >= 0.05, two-sided): "
                    f"QIEA-tuned model RMSE ({mean_rmse_q:.4f}) is comparable to {baseline_name} ({mean_rmse_base:.4f} tonnes)."
                )
        elif mean_rmse_q > mean_rmse_base:
            direction = f"{baseline_name} lower error"
            if is_significant:
                interpretation = (
                    f"Statistically significant difference (p = {p_val:.4f} < 0.05, two-sided): "
                    f"{baseline_name} achieved lower mean RMSE ({mean_rmse_base:.4f} vs {mean_rmse_q:.4f} tonnes)."
                )
            else:
                interpretation = (
                    f"No statistically significant difference (p = {p_val:.4f} >= 0.05, two-sided): "
                    f"{baseline_name} RMSE ({mean_rmse_base:.4f}) is comparable to QIEA ({mean_rmse_q:.4f} tonnes)."
                )
        else:
            direction = "identical error"
            interpretation = (
                f"Identical predictive error (p = 1.0000): both models achieved mean RMSE of {mean_rmse_q:.4f} tonnes."
            )

        significance_tests[baseline_name] = {
            "statistic": float(stat),
            "p_value": float(p_val),
            "is_significant": is_significant,
            "direction": direction,
            "mean_rmse_baseline": mean_rmse_base,
            "mean_rmse_qiea": mean_rmse_q,
            "interpretation": interpretation,
        }

    qiea_obj = models["Quantum-Inspired Predictor"]

    return {
        "metrics": {
            name: {"rmse": v["rmse"], "mae": v["mae"], "r2": v["r2"]}
            for name, v in results.items()
        },
        "significance_tests": significance_tests,
        "test_predictions": pd.DataFrame(test_predictions),
        "qiea_selected_features": qiea_obj.selected_features_,
        "qiea_best_params": qiea_obj.best_params_,
        "qiea_convergence": qiea_obj.convergence_history_,
        "trained_models": models,
        "feature_names": feature_names,
    }
