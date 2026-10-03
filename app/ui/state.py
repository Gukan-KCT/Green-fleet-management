"""
Session state management and cached data loaders for the Green Fleet Platform.
Ensures zero heavy computation on page loads and persists optimized state across navigation.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path
import pickle
import streamlit as st
import pandas as pd

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.analysis.case_study import (
    get_naive_baseline,
    get_best_conventional_baseline,
    run_case_study,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@st.cache_data(show_spinner=False)
def load_saved_pickle(filename: str) -> Optional[Any]:
    """Loads a precomputed pickle artifact from the data directory."""
    path = DATA_DIR / filename
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def get_default_config() -> Dict[str, Any]:
    """Loads central system YAML configuration."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    return st.session_state["config"]


def get_or_load_plan(
    weights: tuple = (0.2, 0.4, 0.4),
    allowed_fuels: Optional[list] = None,
    shore_power: bool = True,
    speed_cap: float = 18.0,
    force_recompute: bool = False,
    pop_size: int = 40,
    generations: int = 150,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Retrieves the active optimized fleet plan from session state or computes it.
    If precomputed case study exists and default settings match, loads instantly.
    """
    state_key = "current_plan_result"

    if not force_recompute and state_key in st.session_state:
        return st.session_state[state_key]

    # Check if precomputed case study is available for default settings
    is_default = (
        weights == (0.2, 0.4, 0.4)
        and allowed_fuels is None
        and shore_power is True
        and speed_cap >= 18.0
    )

    if not force_recompute and is_default:
        saved_case = load_saved_pickle("saved_case_study.pkl")
        if saved_case is not None:
            plan_res = {
                "problem": FleetOptimizationProblem(),
                "optimized_eval": saved_case["optimized_eval"],
                "naive_eval": saved_case["naive_eval"],
                "best_conv_eval": saved_case["best_conv_eval"],
                "df_routes": saved_case["df_routes"],
                "convergence": saved_case["convergence"],
                "best_bits": saved_case["best_bits"],
            }
            st.session_state[state_key] = plan_res
            return plan_res

    # Otherwise compute with current custom settings
    cfg = get_default_config()
    from src.optimization.problem import DEFAULT_CANDIDATE_OPTIONS
    cand_opts = DEFAULT_CANDIDATE_OPTIONS
    if allowed_fuels is not None:
        cand_opts = [o for o in DEFAULT_CANDIDATE_OPTIONS if o["fuel"] in allowed_fuels]
        if not cand_opts:
            cand_opts = DEFAULT_CANDIDATE_OPTIONS

    prob = FleetOptimizationProblem(
        config=cfg,
        candidate_options=cand_opts,
        weights={"fuel": weights[0], "cost": weights[1], "emissions": weights[2]},
        speed_cap_delta=speed_cap - 18.0,
        shore_power_forced=True if shore_power else False,
    )

    # Baselines
    naive_bits, naive_eval = get_naive_baseline(prob)
    best_conv_bits, best_conv_eval = get_best_conventional_baseline(
        prob, pop_size=35, generations=75, random_seed=random_seed
    )

    # QIEA seeded with best conventional baseline
    qiea = QIEA(
        n_bits=prob.n_bits,
        pop_size=pop_size,
        generations=generations,
        rotation_angle=0.06,
        mutation_rate=0.03,
        random_seed=random_seed,
    )
    res = qiea.optimize(prob.fitness_function, seed_bits=best_conv_bits)
    opt_eval = prob.evaluate(res["best_bits"])

    rows = []
    allocs = opt_eval.get("allocations")
    for r_idx, r_key in enumerate(prob.route_keys):
        r_cfg = prob.routes[r_key]
        r_det = opt_eval["route_details"][r_key]

        opt_names = []
        dominant_fuel = "HFO"
        total_vessels = 0
        if allocs is not None:
            for o_idx, opt in enumerate(prob.options):
                n_v = int(allocs[o_idx, r_idx])
                if n_v > 0:
                    opt_names.append(f"{n_v}x {opt['vessel']} ({opt['fuel']})")
                    dominant_fuel = opt["fuel"]
                    total_vessels += n_v

        opt_summary = ", ".join(opt_names) if opt_names else f"1x Handymax ({dominant_fuel})"
        rows.append({
            "Route ID": r_key,
            "Name": r_cfg["name"],
            "Origin": r_cfg["origin"],
            "Destination": r_cfg["destination"],
            "Vessels": max(1, total_vessels),
            "Fuel": dominant_fuel,
            "Option": opt_summary,
            "Speed (knots)": round(r_det.get("speed_knots", 14.0), 1),
            "Capacity (TEU/yr)": int(round(r_det.get("route_cargo_cap", 0))),
            "Demand (TEU/yr)": int(round(r_det.get("annual_demand_teu", 1))),
            "Oversupply Ratio": round(r_det.get("oversupply_ratio", 1.0), 2),
            "Reliability (%)": round(r_det.get("reliability", 95.0), 1),
            "Sailings/Wk": round(r_det.get("sailings_per_week", 1.0), 2),
            "Distance (nm)": r_cfg["distance_nm"],
        })
    df_routes = pd.DataFrame(rows)

    plan_res = {
        "problem": prob,
        "optimized_eval": opt_eval,
        "naive_eval": naive_eval,
        "best_conv_eval": best_conv_eval,
        "df_routes": df_routes,
        "convergence": res["convergence_curve"],
        "best_bits": res["best_bits"],
    }
    st.session_state[state_key] = plan_res
    return plan_res


def get_or_load_prediction_results() -> Optional[Dict[str, Any]]:
    """Loads precomputed fuel prediction benchmark or returns None."""
    if "prediction_results" in st.session_state:
        return st.session_state["prediction_results"]

    saved = load_saved_pickle("saved_prediction_results.pkl")
    if saved is not None:
        st.session_state["prediction_results"] = saved
        return saved
    return None


def get_or_load_benchmark_results() -> Optional[Dict[str, Any]]:
    """Loads precomputed multi-seed algorithmic benchmark or returns None."""
    if "benchmark_results" in st.session_state:
        return st.session_state["benchmark_results"]

    saved = load_saved_pickle("saved_benchmark_results.pkl")
    if saved is not None:
        st.session_state["benchmark_results"] = saved
        return saved
    return None


def get_or_load_scalability_results() -> Optional[pd.DataFrame]:
    """Loads precomputed scalability benchmark or returns None."""
    if "scalability_results" in st.session_state:
        return st.session_state["scalability_results"]

    saved = load_saved_pickle("saved_scalability_results.pkl")
    if saved is not None:
        st.session_state["scalability_results"] = saved
        return saved
    return None


def get_or_load_case_study() -> Optional[Dict[str, Any]]:
    """Loads precomputed case study simulation or returns None."""
    if "case_study_results" in st.session_state:
        return st.session_state["case_study_results"]

    saved = load_saved_pickle("saved_case_study.pkl")
    if saved is not None:
        st.session_state["case_study_results"] = saved
        return saved
    return None
