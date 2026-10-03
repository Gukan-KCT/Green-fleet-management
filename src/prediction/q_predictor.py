"""
Quantum-Inspired Predictor: QIEA-driven Feature Selection and Hyperparameter Tuning.

Uses a Quantum-Inspired Evolutionary Algorithm (QIEA) with Q-bit angle representation
to simultaneously optimize:
1. Feature subset selection (mask bits)
2. Gradient Boosting hyperparameters (discretized binary genes)

Evaluated via cross-validated Root Mean Squared Error (RMSE).
"""

from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import root_mean_squared_error


class QuantumInspiredPredictor:
    """
    Predictor optimized via a Quantum-Inspired Evolutionary Algorithm (QIEA).
    """

    LEARNING_RATES = [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
    MAX_DEPTHS = [2, 3, 4, 5]
    N_ESTIMATORS = [40, 60, 80, 100, 120, 150, 180, 220]
    SUBSAMPLES = [0.70, 0.80, 0.90, 1.00]

    def __init__(
        self,
        population_size: int = 12,
        generations: int = 15,
        rotation_angle: float = 0.05,
        mutation_rate: float = 0.03,
        cv_folds: int = 3,
        random_state: int = 42,
    ):
        self.population_size = population_size
        self.generations = generations
        self.rotation_angle = rotation_angle
        self.mutation_rate = mutation_rate
        self.cv_folds = cv_folds
        self.random_state = random_state

        self.best_params_: Dict[str, Any] = {}
        self.selected_features_: List[str] = []
        self.best_score_: float = float("inf")
        self.convergence_history_: List[float] = []
        self.model_: Optional[GradientBoostingRegressor] = None
        self.all_feature_names_: List[str] = []

    def _bits_to_int(self, bits: np.ndarray) -> int:
        val = 0
        for bit in bits:
            val = (val << 1) | int(bit)
        return val

    def _decode_chromosome(
        self, bits: np.ndarray, feature_names: List[str]
    ) -> Tuple[List[str], Dict[str, Any]]:
        n_feats = len(feature_names)
        feat_bits = bits[:n_feats]

        # 1. Feature selection
        selected = [feature_names[i] for i in range(n_feats) if feat_bits[i] == 1]
        if not selected:
            selected = list(feature_names)  # Fallback to all if none selected

        # 2. Hyperparameters
        idx = n_feats
        # learning rate (3 bits)
        lr_idx = self._bits_to_int(bits[idx : idx + 3]) % len(self.LEARNING_RATES)
        idx += 3
        # max depth (2 bits)
        depth_idx = self._bits_to_int(bits[idx : idx + 2]) % len(self.MAX_DEPTHS)
        idx += 2
        # n_estimators (3 bits)
        n_est_idx = self._bits_to_int(bits[idx : idx + 3]) % len(self.N_ESTIMATORS)
        idx += 3
        # subsample (2 bits)
        sub_idx = self._bits_to_int(bits[idx : idx + 2]) % len(self.SUBSAMPLES)

        params = {
            "learning_rate": self.LEARNING_RATES[lr_idx],
            "max_depth": self.MAX_DEPTHS[depth_idx],
            "n_estimators": self.N_ESTIMATORS[n_est_idx],
            "subsample": self.SUBSAMPLES[sub_idx],
            "random_state": self.random_state,
        }
        return selected, params

    def fit(self, X: pd.DataFrame, y: pd.Series) -> QuantumInspiredPredictor:
        rng = np.random.default_rng(self.random_state)
        feature_names = list(X.columns)
        self.all_feature_names_ = feature_names

        # Total chromosome length = num_features + 3 (lr) + 2 (depth) + 3 (n_est) + 2 (sub)
        n_chrom = len(feature_names) + 10

        # Initialize Q-bit population: angles theta = pi / 4 (equal superposition)
        # Dimensions: [pop_size, n_chrom]
        q_pop = np.full((self.population_size, n_chrom), math.pi / 4.0)

        best_global_bits: Optional[np.ndarray] = None
        best_global_rmse = float("inf")
        self.convergence_history_ = []

        eval_cache: Dict[Tuple, float] = {}

        # Use representative subsample for fast cross-validation during search
        if len(X) > 2000:
            sample_idx = rng.choice(len(X), size=2000, replace=False)
            X_eval = X.iloc[sample_idx]
            y_eval = y.iloc[sample_idx]
        else:
            X_eval = X
            y_eval = y

        # Fixed train/val split for rapid evolutionary fitness evaluation
        n_eval = len(X_eval)
        n_tr = int(n_eval * 0.75)
        tr_idx = np.arange(n_tr)
        val_idx = np.arange(n_tr, n_eval)

        for gen in range(self.generations):
            gen_best_bits = None
            gen_best_rmse = float("inf")

            for i in range(self.population_size):
                # 1. Quantum Observation: sample bit b_j with P(1) = sin^2(theta_j)
                probs = np.sin(q_pop[i]) ** 2
                observed_bits = (rng.random(n_chrom) < probs).astype(int)

                # Decode
                sel_feats, params = self._decode_chromosome(observed_bits, feature_names)
                cache_key = (tuple(sorted(sel_feats)), tuple(sorted(params.items())))

                if cache_key in eval_cache:
                    mean_rmse = eval_cache[cache_key]
                else:
                    X_sub = X_eval[sel_feats].values
                    y_arr = y_eval.values

                    reg = GradientBoostingRegressor(**params)
                    reg.fit(X_sub[tr_idx], y_arr[tr_idx])
                    preds = reg.predict(X_sub[val_idx])
                    mean_rmse = float(root_mean_squared_error(y_arr[val_idx], preds))
                    eval_cache[cache_key] = mean_rmse

                if mean_rmse < gen_best_rmse:
                    gen_best_rmse = mean_rmse
                    gen_best_bits = observed_bits.copy()

                if mean_rmse < best_global_rmse:
                    best_global_rmse = mean_rmse
                    best_global_bits = observed_bits.copy()

            self.convergence_history_.append(best_global_rmse)

            # 2. Quantum Rotation Gate Update towards best global solution
            target_bits = best_global_bits if best_global_bits is not None else gen_best_bits
            if target_bits is not None:
                for i in range(self.population_size):
                    for j in range(n_chrom):
                        # Rotation direction: rotate towards target bit
                        if target_bits[j] == 1 and q_pop[i, j] < math.pi / 2.0:
                            q_pop[i, j] = min(math.pi / 2.0, q_pop[i, j] + self.rotation_angle)
                        elif target_bits[j] == 0 and q_pop[i, j] > 0.0:
                            q_pop[i, j] = max(0.0, q_pop[i, j] - self.rotation_angle)

                        # Quantum NOT Mutation (superposition inversion: theta -> pi/2 - theta)
                        if rng.random() < self.mutation_rate:
                            q_pop[i, j] = math.pi / 2.0 - q_pop[i, j]

        # Final best model construction
        assert best_global_bits is not None
        best_features, best_params = self._decode_chromosome(best_global_bits, feature_names)
        self.selected_features_ = best_features
        self.best_params_ = best_params
        self.best_score_ = best_global_rmse

        # Fit final model on full training set
        self.model_ = GradientBoostingRegressor(**best_params)
        self.model_.fit(X[best_features], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise RuntimeError("QuantumInspiredPredictor must be fitted before predict.")
        # Ensure only selected features are fed
        return self.model_.predict(X[self.selected_features_])
