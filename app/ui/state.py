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
from src.optimization.planner import optimize_fleet_plan
from src.optimization.qiea import QIEA
from src.analysis.case_study import (
    get_naive_baseline,
    get_best_conventional_baseline,
    run_case_study,
)
from src.utils.hashing import verify_pkl_freshness, compute_code_hash

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@st.cache_data(show_spinner=False)
def load_saved_pickle(filename: str) -> Optional[Any]:
    """Loads a precomputed pickle artifact from the data directory and checks freshness."""
    path = DATA_DIR / filename
    if path.exists():
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
                return data
        except Exception:
            return None
    return None


def check_artifact_staleness(filename: str) -> bool:
    """Returns True if the saved pickle artifact is stale or missing."""
    data = load_saved_pickle(filename)
    if data is None:
        return True
    return not verify_pkl_freshness(data)


def get_default_config() -> Dict[str, Any]:
    """Loads central system YAML configuration."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    return st.session_state["config"]


def build_routes_dataframe(prob: FleetOptimizationProblem, opt_eval: Dict[str, Any]) -> pd.DataFrame:
    """Constructs standardized route assignment and oversupply dataframe from problem and eval dict."""
    rows = []
    allocs = opt_eval.get("allocations")
    for r_idx, r_key in enumerate(prob.route_keys):
        r_cfg = prob.routes[r_key]
        r_det = opt_eval.get("route_details", {}).get(r_key, {})

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
    return pd.DataFrame(rows)


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
    Retrieves the active optimized fleet plan from session state or computes it using
    the unified optimize_fleet_plan engine (multi-start unseeded QIEA).
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
            prob = FleetOptimizationProblem()
            opt_eval = saved_case.get("balanced_eval", saved_case.get("optimized_eval"))
            df_routes = build_routes_dataframe(prob, opt_eval)
            plan_res = {
                "problem": prob,
                "optimized_eval": opt_eval,
                "selected_plan": opt_eval,
                "naive_eval": saved_case["naive_eval"],
                "best_conv_eval": saved_case["best_conv_eval"],
                "balanced_eval": saved_case.get("balanced_eval", opt_eval),
                "green_eval": saved_case.get("green_eval"),
                "df_routes": df_routes,
                "convergence": saved_case.get("convergence", saved_case.get("convergence_curve", [])),
                "best_bits": saved_case.get("balanced_bits", saved_case.get("best_bits", saved_case.get("optimized_bits", []))),
                "winner_status": saved_case.get("summary", {}).get("winner_status_balanced", "Green plan selected"),
            }
            st.session_state[state_key] = plan_res
            return plan_res

    # Otherwise compute with current custom settings via unified optimizer
    cfg = get_default_config()
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

    opt_dict = optimize_fleet_plan(
        problem=prob,
        num_qiea_starts=5,
        evals_per_start=4000,
        seeds=[random_seed, random_seed + 1, random_seed + 2, random_seed + 3, random_seed + 4],
    )

    opt_eval = opt_dict["selected_plan"]
    df_routes = build_routes_dataframe(prob, opt_eval)

    plan_res = {
        "problem": prob,
        "optimized_eval": opt_eval,
        "selected_plan": opt_eval,
        "naive_eval": opt_dict["naive_eval"],
        "best_conv_eval": opt_dict["best_conv_eval"],
        "df_routes": df_routes,
        "convergence": opt_dict["convergence_curve"],
        "best_bits": opt_dict["selected_bits"],
        "winner_status": opt_dict["winner_status"],
        "has_green_fuel": opt_dict["has_green_fuel"],
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
        df = saved["data"] if isinstance(saved, dict) and "data" in saved else saved
        st.session_state["scalability_results"] = df
        return df
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
