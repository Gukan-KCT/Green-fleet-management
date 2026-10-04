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
from src.models.network import (
    load_ports_catalog,
    get_demo_network,
    calculate_haversine_distance_nm,
    build_problem_from_network,
    Network,
    PortDefinition,
    RouteDefinition,
    explain_infeasibility,
)
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
 
@app.get("/api/ports-catalog")
@app.get("/api/network-catalog")
def get_ports_catalog():
    """Returns the catalog of 20+ real-world global maritime ports and demo network defaults."""
    catalog = load_ports_catalog()
    demo_net = get_demo_network()
    return clean_json({
        "catalog": catalog,
        "catalog_ports": catalog,
        "demo_network": demo_net.to_dict(),
    })

@app.get("/api/calculate-distance")
def calculate_distance(
    lat1: float = Query(...),
    lon1: float = Query(...),
    lat2: float = Query(...),
    lon2: float = Query(...),
    detour_factor: float = Query(1.15),
):
    """Calculates nautical distance with maritime detour factor."""
    dist = calculate_haversine_distance_nm(lat1, lon1, lat2, lon2, detour_factor)
    return clean_json({"distance_nm": round(dist, 1)})

@app.post("/api/optimize-network")
def optimize_custom_network(network_data: Dict[str, Any] = Body(...)):
    """Optimizes fleet deployment for a custom user-defined network."""
    try:
        net = Network.model_validate(network_data)
        prob = build_problem_from_network(net)
        opt_res = optimize_fleet_plan(
            problem=prob,
            num_qiea_starts=4,
            evals_per_start=3000,
            seeds=[42, 43, 44, 45],
        )
        opt_eval = opt_res["selected_plan"]
        routes = build_routes_df(prob, opt_eval)
        infeasibility_msg = None
        if not opt_eval.get("is_feasible", True):
            infeasibility_msg = explain_infeasibility(prob, opt_eval)

        return clean_json({
            "optimized_eval": opt_eval,
            "naive_eval": opt_res["naive_eval"],
            "best_conv_eval": opt_res["best_conv_eval"],
            "df_routes": routes,
            "winner_status": opt_res["winner_status"],
            "infeasibility_suggestion": infeasibility_msg,
            "is_precomputed": False,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        num_qiea_starts=2,
        evals_per_start=1000,
        seeds=[42, 43],
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

from src.prediction.fuel_model import FuelModel
from src.models.physics import (
    calculate_alternative_fuel_mass,
    calculate_emissions,
    get_fuel_price_usd_per_tonne,
)
from src.analysis.decision_support import compute_carbon_intensity_rating

# Preload ML predictor instances
_prediction_cache: Optional[Dict[str, Any]] = None

def get_prediction_cache() -> Optional[Dict[str, Any]]:
    global _prediction_cache
    if _prediction_cache is None:
        _prediction_cache = load_pkl("saved_prediction_results.pkl")
    return _prediction_cache

@app.get("/api/predict-fuel")
def predict_fuel(
    vessel: str = Query("handymax_feeder"),
    speed: float = Query(14.0, ge=1.0, le=40.0),
    load_factor: float = Query(80.0, ge=0.0, le=100.0),
    weather: float = Query(0.3, ge=0.0, le=1.0),
    distance: float = Query(890.0, ge=1.0, le=25000.0),
    fuel_type: str = Query("HFO"),
    pathway: Optional[str] = Query("default"),
    fuel_price: Optional[float] = Query(None, ge=0.0),
    carbon_tax: Optional[float] = Query(None, ge=0.0),
    model_choice: str = Query("Quantum-Inspired Predictor"),
    mode: str = Query("both"),  # 'ml', 'physics', or 'both'
):
    """
    Calculates operational fuel consumption, lifecycle emissions, voyage cost,
    and carbon intensity comparing real trained ML models and naval physics.
    """
    # Safely unwrap default values if called directly as a Python function
    from fastapi.params import Query as QueryParam
    if isinstance(vessel, QueryParam): vessel = "handymax_feeder"
    if isinstance(speed, QueryParam): speed = 14.0
    if isinstance(load_factor, QueryParam): load_factor = 80.0
    if isinstance(weather, QueryParam): weather = 0.3
    if isinstance(distance, QueryParam): distance = 890.0
    if isinstance(fuel_type, QueryParam): fuel_type = "HFO"
    if isinstance(pathway, QueryParam): pathway = "default"
    if isinstance(fuel_price, QueryParam): fuel_price = None
    if isinstance(carbon_tax, QueryParam): carbon_tax = None
    if isinstance(model_choice, QueryParam): model_choice = "Quantum-Inspired Predictor"
    if isinstance(mode, QueryParam): mode = "both"

    cfg = load_config()
    vessel_keys = list(cfg["vessel_types"].keys())
    if vessel not in cfg["vessel_types"]:
        # Fallback to closest known or handymax
        vessel = "handymax_feeder" if "handymax_feeder" in cfg["vessel_types"] else vessel_keys[0]

    v_info = cfg["vessel_types"][vessel]
    v_cap_dwt = float(v_info.get("capacity_dwt", v_info.get("l_ref_tonnes", 20000.0)))
    cargo_load_tonnes = (max(0.0, min(100.0, float(load_factor))) / 100.0) * v_cap_dwt

    # Validate fuel type
    fuels_cfg = cfg.get("fuels", {})
    if fuel_type not in fuels_cfg:
        fuel_type = "HFO"

    if carbon_tax is None:
        carbon_tax = float(cfg.get("general", {}).get("carbon_price_usd_per_tonne", 80.0))
    else:
        carbon_tax = float(carbon_tax)

    if fuel_price is None or float(fuel_price) <= 0:
        fuel_price = get_fuel_price_usd_per_tonne(fuel_type, pathway, cfg)
    else:
        fuel_price = float(fuel_price)

    speed = float(speed)
    distance = float(distance)
    weather = float(weather)


    # 1. Physics baseline (tonnes conventional HFO)
    phys_fuel_hfo, leg_days = calculate_leg_fuel_conventional(
        vessel_cfg=v_info,
        speed_knots=speed,
        distance_nm=distance,
        cargo_load_tonnes=cargo_load_tonnes,
        weather_severity=weather,
    )

    # Convert physics consumption if alternative fuel requested
    if fuel_type != "HFO":
        phys_fuel_tonnes = calculate_alternative_fuel_mass(phys_fuel_hfo, fuel_type, cfg)
    else:
        phys_fuel_tonnes = phys_fuel_hfo

    # 2. Machine Learning Prediction using actual trained model
    pred_data = get_prediction_cache()
    ml_models = pred_data.get("trained_models", {}) if pred_data else {}
    available_model_names = list(ml_models.keys())

    selected_ml_name = model_choice if model_choice in ml_models else ("Quantum-Inspired Predictor" if "Quantum-Inspired Predictor" in ml_models else (available_model_names[0] if available_model_names else None))

    ml_fuel_hfo = phys_fuel_hfo
    ml_used = False
    if selected_ml_name and selected_ml_name in ml_models:
        try:
            predictor_obj = ml_models[selected_ml_name]
            f_model = FuelModel(
                config=cfg,
                trained_predictor=predictor_obj,
                feature_names=pred_data.get("feature_names"),
                model_name=selected_ml_name,
            )
            ml_fuel_hfo = f_model.predict(
                vessel_type=vessel,
                speed_knots=speed,
                cargo_load_tonnes=cargo_load_tonnes,
                distance_nm=distance,
                weather_severity=weather,
                mode="ml",
            )
            ml_used = True
        except Exception:
            ml_fuel_hfo = phys_fuel_hfo

    if fuel_type != "HFO":
        ml_fuel_tonnes = calculate_alternative_fuel_mass(ml_fuel_hfo, fuel_type, cfg)
    else:
        ml_fuel_tonnes = ml_fuel_hfo

    # Primary predicted fuel according to selected mode
    if mode == "physics":
        primary_fuel = phys_fuel_tonnes
        model_display = "Naval Hydrodynamics (Physics)"
    elif mode == "ml" and ml_used:
        primary_fuel = ml_fuel_tonnes
        model_display = selected_ml_name
    else:
        # Default: ML prediction with physics comparison
        primary_fuel = ml_fuel_tonnes if ml_used else phys_fuel_tonnes
        model_display = selected_ml_name if ml_used else "Naval Hydrodynamics (Physics)"

    diff_tonnes = ml_fuel_tonnes - phys_fuel_tonnes
    diff_pct = ((ml_fuel_tonnes - phys_fuel_tonnes) / max(0.01, phys_fuel_tonnes)) * 100.0

    # 3. Emissions calculation (Well-to-Wake CO2e)
    emiss_dict = calculate_emissions(primary_fuel, fuel_type, pathway, cfg)
    emiss_co2e_t = emiss_dict["total_co2e"]
    ttw_co2e_t = emiss_dict["tank_to_wake"]
    wtt_co2e_t = emiss_dict["well_to_tank"]

    # 4. Voyage Cost calculation
    bunker_cost = primary_fuel * fuel_price
    tax_cost = emiss_co2e_t * carbon_tax
    total_cost = bunker_cost + tax_cost

    # 5. Carbon Intensity (g CO2e / tonne-nm)
    t_nm = max(1.0, cargo_load_tonnes * distance)
    ci_g_tnm = (emiss_co2e_t * 1e6) / t_nm
    ci_info = compute_carbon_intensity_rating(ci_g_tnm)

    # 6. Evaluation metrics for model
    metrics_all = pred_data.get("metrics", {}) if pred_data else {}
    selected_metrics = metrics_all.get(selected_ml_name, {})
    # Strip any non-serializable objects
    clean_metrics = {k: v for k, v in selected_metrics.items() if k != "model_obj"}

    # 7. Speed Sweep Curve comparing ML vs Physics
    v_min = float(v_info.get("v_min_knots", 10.0))
    v_max = float(v_info.get("v_max_knots", 22.0))
    speeds = np.linspace(v_min, v_max, 15).tolist()
    sweep = []
    for sp in speeds:
        p_hfo, _ = calculate_leg_fuel_conventional(v_info, sp, distance, cargo_load_tonnes, weather)
        p_val = calculate_alternative_fuel_mass(p_hfo, fuel_type, cfg) if fuel_type != "HFO" else p_hfo

        m_val = p_val
        if ml_used and selected_ml_name in ml_models:
            try:
                m_hfo = f_model.predict(
                    vessel_type=vessel,
                    speed_knots=sp,
                    cargo_load_tonnes=cargo_load_tonnes,
                    distance_nm=distance,
                    weather_severity=weather,
                    mode="ml",
                )
                m_val = calculate_alternative_fuel_mass(m_hfo, fuel_type, cfg) if fuel_type != "HFO" else m_hfo
            except Exception:
                m_val = p_val

        sweep.append({
            "speed": round(sp, 1),
            "physics_fuel": round(p_val, 2),
            "ml_fuel": round(m_val, 2),
        })

    return clean_json({
        "status": "success",
        "inputs": {
            "vessel": vessel,
            "vessel_name": v_info.get("name", vessel),
            "vessel_capacity_dwt": v_cap_dwt,
            "cargo_tonnes": round(cargo_load_tonnes, 1),
            "load_factor_pct": load_factor,
            "speed_knots": speed,
            "distance_nm": distance,
            "weather_severity": weather,
            "fuel_type": fuel_type,
            "pathway": pathway,
            "fuel_price_usd_t": fuel_price,
            "carbon_tax_usd_t": carbon_tax,
            "model_choice": selected_ml_name,
            "mode": mode,
        },
        "prediction": {
            "fuel_tonnes": round(primary_fuel, 2),
            "model_used": model_display,
            "is_ml": ml_used and mode != "physics",
            "ml_prediction_tonnes": round(ml_fuel_tonnes, 2),
            "physics_estimate_tonnes": round(phys_fuel_tonnes, 2),
            "difference_tonnes": round(diff_tonnes, 2),
            "difference_pct": round(diff_pct, 2),
            "leg_days": round(leg_days, 2),
        },
        "economics": {
            "fuel_cost_usd": round(bunker_cost, 2),
            "carbon_tax_usd": round(tax_cost, 2),
            "total_cost_usd": round(total_cost, 2),
            "fuel_price_usd_per_tonne": round(fuel_price, 2),
            "carbon_price_usd_per_tonne": round(carbon_tax, 2),
        },
        "emissions": {
            "total_co2e_tonnes": round(emiss_co2e_t, 2),
            "tank_to_wake_tonnes": round(ttw_co2e_t, 2),
            "well_to_tank_tonnes": round(wtt_co2e_t, 2),
            "carbon_intensity_g_tnm": round(ci_g_tnm, 2),
            "carbon_intensity_rating": ci_info,
        },
        "model_validation": {
            "model_name": selected_ml_name,
            "mae": clean_metrics.get("mae"),
            "rmse": clean_metrics.get("rmse"),
            "r2": clean_metrics.get("r2"),
            "available_models": available_model_names,
            "all_metrics": {k: {mk: mv for mk, mv in v.items() if mk != "model_obj"} for k, v in metrics_all.items()},
            "qiea_selected_features": pred_data.get("qiea_selected_features", []) if pred_data else [],
            "qiea_best_params": pred_data.get("qiea_best_params", {}) if pred_data else {},
        },
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
    saved = load_pkl("saved_scenarios.pkl")
    if saved:
        return clean_json(saved)
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
