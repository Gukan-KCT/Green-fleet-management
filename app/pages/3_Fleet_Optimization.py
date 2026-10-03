"""
Fleet Optimization Page - Multi-Objective QIEA Engine & Pareto Analysis.
"""

import sys
from pathlib import Path
import pickle
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem
from src.optimization.qiea import QIEA
from src.optimization.pareto import sweep_pareto_front

st.set_page_config(page_title="Fleet Optimization | Green Fleet", page_icon="⚙️", layout="wide")

st.title("⚙️ Fleet Deployment Optimization (QIEA)")
st.markdown("Quantum-Inspired Evolutionary Algorithm for multi-objective vessel allocation, speed optimization, and decarbonization.")

st.info("**SYNTHETIC NOTICE:** Optimization utilizes synthetic fleet parameters, illustrative costs, and regional feeder corridors.")

cfg = load_config()

# Sidebar: Controls
st.sidebar.header("Optimization Controls")

w_fuel = st.sidebar.slider("Weight: Fuel Minimization (w1)", 0.0, 1.0, 0.30, 0.05)
w_cost = st.sidebar.slider("Weight: Operating Cost (w2)", 0.0, 1.0, 0.40, 0.05)
w_emiss = st.sidebar.slider("Weight: Lifecycle Emissions (w3)", 0.0, 1.0, 0.30, 0.05)

w_sum = max(1e-4, w_fuel + w_cost + w_emiss)
w_norm = {"fuel": w_fuel / w_sum, "cost": w_cost / w_sum, "emissions": w_emiss / w_sum}
st.sidebar.caption(f"Normalized Weights: Fuel={w_norm['fuel']:.2f}, Cost={w_norm['cost']:.2f}, Emissions={w_norm['emissions']:.2f}")

pop_size = st.sidebar.slider("Population Size (M)", 10, 50, 25, 5)
generations = st.sidebar.slider("Generations (G)", 15, 60, 35, 5)
seed = st.sidebar.number_input("Random Seed", value=42, step=1)

run_button = st.sidebar.button("🚀 Run Fleet Optimization", width="stretch", type="primary")

saved_case_file = PROJECT_ROOT / "data" / "saved_case_study.pkl"

# Run or retrieve session state (loading precomputed data on initial load for instant <10s display)
if "opt_result" not in st.session_state or run_button:
    if not run_button and saved_case_file.exists():
        try:
            with open(saved_case_file, "rb") as f:
                c_data = pickle.load(f)
            prob = FleetOptimizationProblem(config=cfg, weights=w_norm)
            st.session_state["opt_result"] = {
                "eval": c_data["optimized_eval"],
                "convergence": c_data.get("convergence_curve", [4.0, 3.5, 3.2]),
                "evaluations": c_data.get("evaluations", 10000),
                "problem": prob,
            }
        except Exception:
            prob = FleetOptimizationProblem(config=cfg, weights=w_norm)
            qiea = QIEA(n_bits=prob.n_bits, pop_size=pop_size, generations=generations, random_seed=seed, initial_theta=prob.get_initial_q_angles())
            opt_out = qiea.optimize(prob.fitness_function)
            eval_res = prob.evaluate(opt_out["best_bits"])
            st.session_state["opt_result"] = {
                "eval": eval_res,
                "convergence": opt_out["convergence_curve"],
                "evaluations": opt_out["evaluations"],
                "problem": prob,
            }
    else:
        with st.spinner("Executing Quantum-Inspired Evolutionary Algorithm..."):
            prob = FleetOptimizationProblem(config=cfg, weights=w_norm)
            qiea = QIEA(
                n_bits=prob.n_bits,
                pop_size=pop_size,
                generations=generations,
                random_seed=seed,
                initial_theta=prob.get_initial_q_angles(),
            )
            opt_out = qiea.optimize(prob.fitness_function)
            eval_res = prob.evaluate(opt_out["best_bits"])
            st.session_state["opt_result"] = {
                "eval": eval_res,
                "convergence": opt_out["convergence_curve"],
                "evaluations": opt_out["evaluations"],
                "problem": prob,
            }

res = st.session_state["opt_result"]
ev = res["eval"]
conv = res["convergence"]

# 1. Macro Metrics
st.subheader("1. Optimal Deployment Plan Performance")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Fuel Burn", f"{ev['total_fuel_tonnes_hfo_eq']:,.0f} t", help="HFO-equivalent metric tonnes")
m2.metric("Total Operating Cost", f"${ev['total_operating_cost_usd'] / 1e6:.2f} M", help="Includes fuel, charter, ports, carbon tax")
m3.metric("Lifecycle Emissions", f"{ev['total_emissions_co2e_tonnes'] / 1e3:.2f} kt", help="Well-to-Wake CO2e")
m4.metric("Carbon Intensity", f"{ev['carbon_intensity_g_tnm']:.2f} g/t-nm", help="Regulatory proxy cap = 18.0")
m5.metric("Feasibility", "Feasible ✅" if ev["is_feasible"] else "Violations ⚠️", f"Score: {ev['total_violation_score']:.2f}")

# 2. Visualizations: Convergence & Allocations
vis_col1, vis_col2 = st.columns(2)

with vis_col1:
    st.markdown("##### Optimization Convergence Profile")
    fig_conv = px.line(
        x=list(range(1, len(conv) + 1)),
        y=conv,
        markers=True,
        labels={"x": "Generation", "y": "Penalized Objective Fitness"},
    )
    fig_conv.update_traces(line_color="#059669", marker=dict(size=5))
    fig_conv.update_layout(template="plotly_white", height=320)
    st.plotly_chart(fig_conv, width="stretch")

with vis_col2:
    st.markdown("##### Deployed Fleet Mix by Vessel Type")
    v_counts = ev["vessels_used_by_type"]
    fig_mix = px.bar(
        x=[cfg["vessel_types"][k]["name"] for k in v_counts.keys()],
        y=list(v_counts.values()),
        labels={"x": "Vessel Class", "y": "Vessels Deployed"},
        color=list(v_counts.keys()),
        color_discrete_sequence=px.colors.qualitative.Prism,
    )
    fig_mix.update_layout(template="plotly_white", height=320, showlegend=False)
    st.plotly_chart(fig_mix, width="stretch")

# 3. Route Deployment Table (including Oversupply Ratio)
st.markdown("---")
st.subheader("2. Route Assignment & Operational Service Profile")

r_rows = []
for rk, r_det in ev["route_details"].items():
    rcfg = cfg["routes"][rk]
    r_rows.append({
        "Route ID": rk,
        "Corridor Name": rcfg["name"],
        "Cruising Speed (kn)": r_det["speed_knots"],
        "Vessels Assigned": r_det["vessels_assigned"],
        "Supplied Cap (TEU)": f"{r_det['annual_capacity_teu']:,.0f}",
        "Cargo Moved (TEU)": f"{r_det.get('cargo_moved_teu', min(r_det['annual_capacity_teu'], r_det['annual_demand_teu'])):,.0f}",
        "Required Demand": f"{r_det['annual_demand_teu']:,.0f}",
        "Oversupply Ratio": f"{r_det.get('oversupply_ratio', 1.0):.2f}",
        "Sailings/Week": f"{r_det['sailings_per_week']:.2f}",
        "Min Required": f"{r_det['min_sailings_per_week']:.1f}",
        "Reliability Index": f"{r_det['reliability']:.2f}",
        "Status": "Compliant" if r_det["annual_capacity_teu"] >= r_det["annual_demand_teu"] else "Demand Shortfall",
    })
st.dataframe(pd.DataFrame(r_rows), width="stretch")

# 4. Multi-Objective Pareto Frontier
st.markdown("---")
st.subheader("3. Multi-Objective Pareto Frontier Sweep")
st.markdown("Explores the trade-off frontier between Fuel, Cost, and Decarbonization by sweeping diverse objective weight vectors:")

if st.button("🔄 Compute Multi-Objective Pareto Front"):
    with st.spinner("Sweeping multi-objective weight grid with QIEA..."):
        all_sols, p_front = sweep_pareto_front(
            problem_base=res["problem"],
            pop_size=15,
            generations=20,
            random_seed=42,
        )
        st.session_state["pareto_data"] = (all_sols, p_front)

if "pareto_data" in st.session_state:
    all_sols, p_front = st.session_state["pareto_data"]

    p_df = pd.DataFrame([
        {
            "Fuel (t HFO-eq)": s["total_fuel_tonnes_hfo_eq"],
            "Operating Cost ($M)": s["total_operating_cost_usd"] / 1e6,
            "Emissions (kt CO2e)": s["total_emissions_co2e_tonnes"] / 1000.0,
            "Weight Profile": s.get("weight_label", "Custom"),
            "Is Pareto Optimal": "Yes (Pareto Front)" if s in p_front else "No (Dominated)",
        }
        for s in all_sols
    ])

    fig_pareto = px.scatter_3d(
        p_df,
        x="Fuel (t HFO-eq)",
        y="Operating Cost ($M)",
        z="Emissions (kt CO2e)",
        color="Is Pareto Optimal",
        hover_data=["Weight Profile"],
        color_discrete_map={"Yes (Pareto Front)": "#059669", "No (Dominated)": "#94a3b8"},
        title="3D Multi-Objective Trade-Off Space",
    )
    fig_pareto.update_layout(template="plotly_white", height=500)
    st.plotly_chart(fig_pareto, width="stretch")

    st.markdown(f"**Identified {len(p_front)} non-dominated Pareto-optimal policies** across {len(all_sols)} weight combinations.")
