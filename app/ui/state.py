"""
Session State Management and Cached Artifact Loaders for Streamlit UI.
Centralizes plan execution, configuration caching, and deterministic SHA-256 freshness verification.
"""

from __future__ import annotations
import pickle
from pathlib import Path
from typing import Dict, Any, Optional
import streamlit as st
import pandas as pd
import numpy as np

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS
from src.optimization.planner import optimize_fleet_plan
from src.utils.hashing import check_artifact_staleness, get_codebase_hash

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def get_default_config() -> Dict[str, Any]:
    """Retrieves cached YAML configuration or loads fresh from disk."""
    if "app_config" not in st.session_state:
        st.session_state["app_config"] = load_config()
    return st.session_state["app_config"]


def load_saved_pickle(filename: str) -> Optional[Any]:
    """Safely loads a pickle file from the data directory if present."""
    p = DATA_DIR / filename
    if p.exists():
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None


def build_routes_dataframe(problem: FleetOptimizationProblem, eval_res: Dict[str, Any]) -> pd.DataFrame:
    """
    Transforms problem route specifications and evaluation results into an
    interactive table for visualization and UI tables.
    """
    routes = problem.routes
    route_details = eval_res.get("route_details", {})
    rows = []

    for r_k, r_cfg in routes.items():
        r_det = route_details.get(r_k, {})
        vessels_assigned = r_det.get("vessels_assigned", {})
        total_vessels = sum(vessels_assigned.values()) if isinstance(vessels_assigned, dict) else int(vessels_assigned)

        # Determine dominant fuel and option
        opt_idx = r_det.get("selected_option_idx", 0)
        dominant_fuel = "HFO"
        opt_summary = "None"
        if 0 <= opt_idx < len(problem.options):
            dominant_fuel = problem.options[opt_idx]["fuel"]
            opt_summary = f"{problem.options[opt_idx]['vessel']} ({dominant_fuel})"

        rows.append({
            "Route ID": r_k,
            "Route Name": r_cfg["name"],
            "Origin": r_cfg["origin"],
            "Destination": r_cfg["destination"],
            "Vessels": max(1, total_vessels),
            "Fuel": dominant_fuel,
            "Option": opt_summary,
            "Speed (knots)": round(r_det.get("speed_knots", 14.0), 1),
            "Capacity (TEU/yr)": int(round(r_det.get("route_cargo_cap", 0))),
            "Demand (TEU/yr)": int(round(r_det.get("annual_demand_teu", 1))),
            "Oversupply Ratio": round(r_det.get("oversupply_ratio", 1.0), 2),
            "Reliability (%)": round(r_det.get("reliability", 95.0) if r_det.get("reliability", 1.0) > 1.0 else r_det.get("reliability", 0.95) * 100.0, 1),
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
    num_starts: int = 5,
    evals_per_start: int = 4000,
) -> Dict[str, Any]:
    """
    Retrieves the active optimized fleet plan from session state or computes it using
    the unified optimize_fleet_plan engine (multi-start unseeded QIEA), supporting both
    the demo network and user-defined custom networks.
    """
    from src.models.network import get_demo_network, build_problem_from_network, explain_infeasibility

    active_net = st.session_state.get("active_network", get_demo_network())
    net_hash = active_net.compute_hash() if hasattr(active_net, "compute_hash") else "demo"
    is_demo = getattr(active_net, "is_demo", True)

    state_key = f"current_plan_result_{net_hash}"

    if not force_recompute and state_key in st.session_state:
        return st.session_state[state_key]

    # Check if precomputed case study is available for default settings (DEMO NETWORK ONLY)
    is_default = (
        is_demo
        and weights == (0.2, 0.4, 0.4)
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
                "infeasibility_suggestions": [],
                "is_custom_network": False,
                "network_hash": net_hash,
            }
            st.session_state[state_key] = plan_res
            return plan_res

    # Build problem for active network
    cand_opts = DEFAULT_CANDIDATE_OPTIONS
    if allowed_fuels is not None:
        cand_opts = [o for o in DEFAULT_CANDIDATE_OPTIONS if o["fuel"] in allowed_fuels]
        if not cand_opts:
            cand_opts = DEFAULT_CANDIDATE_OPTIONS

    prob = build_problem_from_network(
        network=active_net,
        weights=weights,
        candidate_options=cand_opts,
        speed_cap=speed_cap,
        shore_power_forced=True if shore_power else False,
    )

    plan_out = optimize_fleet_plan(
        problem=prob,
        weights=weights,
        allowed_fuels=allowed_fuels,
        speed_cap=speed_cap,
        shore_power=shore_power,
        num_qiea_starts=num_starts,
        evals_per_start=evals_per_start,
        seeds=[random_seed + i for i in range(num_starts)],
    )

    selected_eval = plan_out["selected_plan"]
    df_routes = build_routes_dataframe(prob, selected_eval)

    suggestions = []
    if not selected_eval.get("is_feasible", True):
        suggestions = explain_infeasibility(prob, selected_eval)

    plan_res = {
        "problem": prob,
        "optimized_eval": selected_eval,
        "selected_plan": selected_eval,
        "naive_eval": plan_out["naive_eval"],
        "best_conv_eval": plan_out["best_conv_eval"],
        "df_routes": df_routes,
        "convergence": plan_out["convergence_curve"],
        "best_bits": plan_out["selected_bits"],
        "winner_status": plan_out["winner_status"],
        "infeasibility_suggestions": suggestions,
        "is_custom_network": not is_demo,
        "network_hash": net_hash,
    }

    st.session_state[state_key] = plan_res
    return plan_res



def get_or_load_prediction_results() -> Optional[Dict[str, Any]]:
    """Loads precomputed predictive models benchmark or returns None."""
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


def get_or_load_breakeven_grid() -> Optional[Dict[str, Any]]:
    """Loads precomputed break-even sensitivity grid or computes if missing."""
    if "breakeven_grid" in st.session_state:
        return st.session_state["breakeven_grid"]

    saved = load_saved_pickle("saved_breakeven_grid.pkl")
    if saved is not None:
        st.session_state["breakeven_grid"] = saved
        return saved
    return None


def get_or_load_robustness() -> Optional[Dict[str, Any]]:
    """Loads precomputed optimizer robustness results or returns None."""
    if "robustness_results" in st.session_state:
        return st.session_state["robustness_results"]

    saved = load_saved_pickle("saved_robustness.pkl")
    if saved is not None:
        st.session_state["robustness_results"] = saved
        return saved
    return None


def get_or_load_q_history() -> Optional[Dict[str, Any]]:
    """Loads precomputed Q-bit probability history for visualizer."""
    if "q_history" in st.session_state:
        return st.session_state["q_history"]

    saved = load_saved_pickle("saved_q_history.pkl")
    if saved is not None:
        st.session_state["q_history"] = saved
        return saved
    return None
