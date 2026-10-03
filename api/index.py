"""
FastAPI Serverless API & Web Application for Green Fleet.
Serves static frontend and lightweight, high-performance REST endpoints
compatible with Vercel Serverless Functions.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import pickle
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config, calculate_leg_fuel_conventional
from src.analysis.fuels import compare_fuels_for_voyage
from src.analysis.shore_power import analyze_shore_power_fleet
from src.analysis.scenarios import run_all_preset_scenarios, evaluate_scenario, PRESET_SCENARIOS
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.analysis.case_study import get_naive_baseline, get_best_conventional_baseline

app = FastAPI(
    title="Green Fleet Management API",
    description="Decarbonization, techno-economic optimization & physics modeling engine for maritime logistics.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = PROJECT_ROOT / "data"

def clean_json(obj: Any) -> Any:
    """Recursively converts NumPy/Pandas objects into native JSON serializable types."""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [clean_json(x) for x in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    return obj

def load_pkl(name: str) -> Optional[Any]:
    p = DATA_DIR / name
    if p.exists():
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

from src.optimization.planner import optimize_fleet_plan

def build_routes_df(prob: FleetOptimizationProblem, opt_eval: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    allocs = opt_eval.get("allocations")
    for r_idx, r_key in enumerate(prob.route_keys):
        r_cfg = prob.routes[r_key]
        r_det = opt_eval.get("route_details", {}).get(r_key, {})

        opt_names = []
        dominant_fuel = None
        total_vessels = 0
        if allocs is not None:
            for o_idx, opt in enumerate(prob.options):
                n_v = int(allocs[o_idx, r_idx])
                if n_v > 0:
                    opt_names.append(f"{n_v}x {opt['vessel']} ({opt['fuel']})")
                    dominant_fuel = opt["fuel"]
                    total_vessels += n_v

        opt_summary = ", ".join(opt_names) if opt_names else "No vessels assigned"
        dominant_fuel = dominant_fuel if dominant_fuel else "None"

        # Reliability in 0-100 range
        raw_rel = r_det.get("reliability")
        rel_pct = round(raw_rel * 100.0, 1) if raw_rel is not None else None

        rows.append({
            "Route ID": r_key,
            "Name": r_cfg["name"],
            "Origin": r_cfg["origin"],
            "Destination": r_cfg["destination"],
            "Vessels": total_vessels,
            "vessels": total_vessels,
            "Fuel": dominant_fuel,
            "fuel": dominant_fuel,
            "Option": opt_summary,
            "Speed (knots)": round(r_det.get("speed_knots", 14.0), 1) if r_det.get("speed_knots") is not None else None,
            "Capacity (TEU/yr)": int(round(r_det.get("route_cargo_cap", 0))) if r_det.get("route_cargo_cap") is not None else 0,
            "Demand (TEU/yr)": int(round(r_det.get("annual_demand_teu", 1))),
            "Oversupply Ratio": round(r_det.get("oversupply_ratio", 0.0), 2) if r_det.get("oversupply_ratio") is not None else 0.0,
            "Reliability (%)": rel_pct,
            "reliability": rel_pct if rel_pct is not None else 0.0,
            "Sailings/Wk": round(r_det.get("sailings_per_week", 0.0), 2) if r_det.get("sailings_per_week") is not None else 0.0,
            "Distance (nm)": r_cfg["distance_nm"],
        })
    return rows

# --- API Endpoints ---

@app.get("/api/config")
def get_system_config():
    """Returns the central vessel, route, port, and environmental configuration."""
    return clean_json(load_config())

@app.get("/api/plan")
def get_plan(
    w_fuel: float = Query(0.2, ge=0.0, le=1.0),
    w_cost: float = Query(0.4, ge=0.0, le=1.0),
    w_emiss: float = Query(0.4, ge=0.0, le=1.0),
    speed_cap: float = Query(18.0, ge=10.0, le=25.0),
    shore_power: bool = Query(True),
    force_recompute: bool = Query(False),
):
    """Calculates or retrieves precomputed multi-objective fleet optimization plan via unified optimize_fleet_plan."""
    # Normalize weights
    total_w = w_fuel + w_cost + w_emiss
    if total_w > 0:
        w_fuel, w_cost, w_emiss = w_fuel / total_w, w_cost / total_w, w_emiss / total_w
    else:
        w_fuel, w_cost, w_emiss = 0.2, 0.4, 0.4

    is_default = (
        abs(w_fuel - 0.2) < 1e-3
        and abs(w_cost - 0.4) < 1e-3
        and abs(w_emiss - 0.4) < 1e-3
        and shore_power is True
        and speed_cap >= 18.0
        and not force_recompute
    )

    if is_default:
        saved = load_pkl("saved_case_study.pkl")
        if saved:
            prob = FleetOptimizationProblem()
            opt_eval = saved.get("balanced_eval", saved.get("optimized_eval"))
            routes = build_routes_df(prob, opt_eval)
            return clean_json({
                "optimized_eval": opt_eval,
                "naive_eval": saved["naive_eval"],
                "best_conv_eval": saved["best_conv_eval"],
                "df_routes": routes,
                "winner_status": saved.get("summary", {}).get("winner_status_balanced", "Green plan selected"),
                "convergence": saved.get("convergence", saved.get("convergence_curve", [])),
                "is_precomputed": True,
            })

    cfg = load_config()
    prob = FleetOptimizationProblem(
        config=cfg,
        weights={"fuel": w_fuel, "cost": w_cost, "emissions": w_emiss},
        speed_cap_delta=speed_cap - 18.0,
        shore_power_forced=shore_power,
    )

    opt_res = optimize_fleet_plan(
        problem=prob,
        num_qiea_starts=5,
        evals_per_start=4000,
        seeds=[42, 43, 44, 45, 46],
    )
    opt_eval = opt_res["selected_plan"]
    routes = build_routes_df(prob, opt_eval)

    return clean_json({
        "optimized_eval": opt_eval,
        "naive_eval": opt_res["naive_eval"],
        "best_conv_eval": opt_res["best_conv_eval"],
        "df_routes": routes,
        "winner_status": opt_res["winner_status"],
        "convergence": opt_res["convergence_curve"],
        "is_precomputed": False,
    })

@app.get("/api/predict-fuel")
def predict_fuel(
    vessel: str = Query("handymax_feeder"),
    speed: float = Query(14.0),
    load_factor: float = Query(80.0),
    weather: float = Query(0.3),
    distance: float = Query(890.0),
    fuel_price: float = Query(650.0),
    carbon_tax: float = Query(50.0),
):
    """Calculates instantaneous voyage fuel, cost, emissions, and ML regression comparison."""
    cfg = load_config()
    v_info = cfg["vessel_types"].get(vessel, cfg["vessel_types"]["handymax_feeder"])
    cargo_load = (load_factor / 100.0) * float(v_info["l_ref_tonnes"])
    
    fuel_t, leg_days = calculate_leg_fuel_conventional(
        vessel_cfg=v_info,
        speed_knots=speed,
        distance_nm=distance,
        cargo_load_tonnes=cargo_load,
        weather_severity=weather,
    )
    
    cf_co2 = float(cfg["fuels"]["HFO"].get("cf_co2", 3.114))
    emiss_t = fuel_t * cf_co2
    fuel_cost = fuel_t * fuel_price
    tax_cost = emiss_t * carbon_tax
    total_cost = fuel_cost + tax_cost
    
    # Load ML metrics
    pred_data = load_pkl("saved_prediction_results.pkl")
    metrics = pred_data.get("metrics", {}) if pred_data else {}
    
    # Generate speed sweep curve
    speeds = np.linspace(float(v_info["v_min_knots"]), float(v_info["v_max_knots"]), 15).tolist()
    sweep = []
    for sp in speeds:
        f_t, _ = calculate_leg_fuel_conventional(v_info, sp, distance, cargo_load, weather)
        sweep.append({"speed": round(sp, 1), "fuel": round(f_t, 2)})

    return clean_json({
        "fuel_tonnes": round(fuel_t, 2),
        "leg_days": round(leg_days, 2),
        "emissions_co2e_t": round(emiss_t, 2),
        "fuel_cost_usd": round(fuel_cost, 2),
        "carbon_tax_usd": round(tax_cost, 2),
        "total_cost_usd": round(total_cost, 2),
        "ml_metrics": metrics,
        "speed_sweep": sweep,
    })

@app.get("/api/alternative-fuels")
def get_alternative_fuels(
    vessel: str = Query("handymax_feeder"),
    route: str = Query("R1"),
    pathway: str = Query("green"),
):
    """Evaluates comparative energy density, cargo displacement, and lifecycle GHG per fuel."""
    cfg = load_config()
    pathways = {f: pathway for f in ["Methanol", "Ammonia", "Hydrogen"]}
    df = compare_fuels_for_voyage(
        vessel_key=vessel,
        route_key=route,
        pathway_choices=pathways,
        config=cfg,
    )
    return clean_json(df.to_dict(orient="records"))

@app.get("/api/shore-power")
def get_shore_power():
    """Returns cold-ironing port connectivity, tariff, and auxiliary emissions displacement."""
    saved = load_pkl("saved_shore_power.pkl")
    cfg = load_config()
    return clean_json({
        "data": saved,
        "ports": cfg.get("ports", {}),
    })

@app.get("/api/scenarios")
def get_scenarios():
    """Runs or returns precomputed policy & climate stress testing scenarios."""
    cfg = load_config()
    summary_df, details_map = run_all_preset_scenarios(config=cfg)
    return clean_json(details_map)

@app.get("/api/benchmark")
def get_benchmark():
    """Returns algorithmic multi-seed benchmark & scalability results across QIEA, GA, PSO."""
    bench = load_pkl("saved_benchmark_results.pkl")
    scal = load_pkl("saved_scalability_results.pkl")
    return clean_json({
        "benchmark": bench,
        "scalability": scal,
    })

@app.get("/api/case-study")
def get_case_study():
    """Returns comprehensive South Asian feeder network case study simulation."""
    saved = load_pkl("saved_case_study.pkl")
    return clean_json(saved)

# --- Mount Static Frontend ---
PUBLIC_DIR = PROJECT_ROOT / "public"
if PUBLIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = PUBLIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Green Fleet Management System</h1><p>API is active. Frontend is loading...</p>")
