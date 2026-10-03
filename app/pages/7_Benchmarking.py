"""
Benchmarking Page - QIEA vs GA vs PSO vs Random Search & Network Scalability.
"""

import sys
from pathlib import Path
import pickle
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem
from src.analysis.benchmark import (
    run_benchmark_suite,
    run_scalability_analysis,
    DEFAULT_BENCHMARK_SEEDS,
)
from src.prediction.evaluator import evaluate_prediction_models

st.set_page_config(page_title="Benchmarking | Green Fleet", page_icon="📊", layout="wide")

st.title("📊 Algorithmic Benchmarking & Scalability")
st.markdown("Controlled multi-seed empirical comparison of the Quantum-Inspired Evolutionary Algorithm (QIEA) against classical baselines (GA, PSO, and Random Search).")

st.info(
    """
    **BENCHMARK FAIRNESS & HONESTY GUARANTEE:**  
    All algorithms evaluate the identical objective function, bitstring decoding pipeline, and evaluation budget across identical random seeds. Narratives and rankings are derived purely from empirical metrics without pre-determined winners.
    """
)

cfg = load_config()

# Sidebar Controls
st.sidebar.header("Benchmarking Controls")
rerun_btn = st.sidebar.button("🔄 Re-run Benchmark Suite", width="stretch", type="primary")

data_dir = PROJECT_ROOT / "data"
saved_bench_file = data_dir / "saved_benchmark_results.pkl"
saved_scale_file = data_dir / "saved_scalability_results.pkl"
saved_pred_file = data_dir / "saved_prediction_results.pkl"


@st.cache_data(show_spinner="Evaluating algorithmic benchmark (10 seeds, 20k evals)...")
def get_benchmark_data(force_recompute: bool = False):
    if not force_recompute and saved_bench_file.exists():
        try:
            with open(saved_bench_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    prob = FleetOptimizationProblem(config=cfg)
    return run_benchmark_suite(
        problem=prob,
        seeds=DEFAULT_BENCHMARK_SEEDS,
        pop_size=50,
        generations=400,
    )


@st.cache_data(show_spinner="Evaluating scalability across Small (39b), Med (101b), Large (462b)...")
def get_scalability_data(force_recompute: bool = False):
    if not force_recompute and saved_scale_file.exists():
        try:
            with open(saved_scale_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return run_scalability_analysis(seeds=DEFAULT_BENCHMARK_SEEDS, config=cfg)


@st.cache_data(show_spinner="Evaluating prediction benchmark (repeated 10-fold CV)...")
def get_prediction_data(force_recompute: bool = False):
    if not force_recompute and saved_pred_file.exists():
        try:
            with open(saved_pred_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return evaluate_prediction_models(
        csv_path=str(data_dir / "synthetic_fuel.csv"),
        qiea_pop_size=15,
        qiea_generations=20,
        random_seed=42,
    )


if rerun_btn:
    st.cache_data.clear()
    bench_data = get_benchmark_data(force_recompute=True)
    df_scale = get_scalability_data(force_recompute=True)
    p_data = get_prediction_data(force_recompute=True)
else:
    bench_data = get_benchmark_data(force_recompute=False)
    df_scale = get_scalability_data(force_recompute=False)
    p_data = get_prediction_data(force_recompute=False)

tab_algo, tab_scale, tab_pred = st.tabs([
    "1. Optimization Benchmark (QIEA vs GA vs PSO vs RS)",
    "2. Problem Scalability (Small vs Medium vs Large 24-Route)",
    "3. Prediction ML Benchmark",
])

colors = {
    "Genetic Algorithm (GA)": "#2563eb",
    "QIEA (Quantum-Inspired)": "#059669",
    "Particle Swarm (PSO)": "#d97706",
    "Random Search": "#94a3b8",
}

with tab_algo:
    st.subheader(f"1. Multi-Seed Optimization Performance (Medium 5-Route Problem, L={bench_data['n_bits']} Bits)")
    st.markdown(
        f"Evaluated across **{len(bench_data['eval_seeds'])} independent seeds** with **{bench_data['pop_size'] * bench_data['generations']:,} function evaluations** per algorithm."
    )

    df_summary = bench_data["summary"]
    mean_conv = bench_data["mean_convergence"]

    st.dataframe(df_summary, width="stretch")

    # Convergence Curves Plot
    st.markdown("##### Mean Convergence Curves Across Independent Seeds")
    fig_conv = go.Figure()

    for alg_name, curve in mean_conv.items():
        fig_conv.add_trace(
            go.Scatter(
                x=list(range(1, len(curve) + 1)),
                y=curve,
                mode="lines",
                name=alg_name,
                line=dict(color=colors.get(alg_name, "#000000"), width=2.5),
            )
        )

    fig_conv.update_layout(
        xaxis_title="Generation",
        yaxis_title="Mean Penalized Fitness (Lower is Better)",
        template="plotly_white",
        height=420,
    )
    st.plotly_chart(fig_conv, width="stretch")

    st.markdown("---")
    st.markdown("##### Data-Driven Algorithmic Evaluation")
    st.markdown(bench_data.get("narrative", ""))

with tab_scale:
    st.subheader("2. Network Dimension Scalability Analysis")
    st.markdown("Evaluates runtime scaling and optimization quality across 3 network tiers (10 seeds each):")
    st.markdown("- **Small Tier:** 3 Corridors, 4 Candidate options ($L = 39$ decision bits, 8,000 evals)")
    st.markdown("- **Medium Tier (Default):** 5 Corridors, 8 Candidate options ($L = 101$ decision bits, 20,000 evals)")
    st.markdown("- **Large Tier:** 24 Synthetic Corridors, 8 Candidate options ($L = 462$ decision bits, 30,000 evals)")

    st.dataframe(df_scale, width="stretch")

    # Runtime vs Problem Size
    st.markdown("##### Execution Runtime Scaling by Problem Size")
    fig_scale = px.bar(
        df_scale,
        x="Scale",
        y="Avg Runtime (s)",
        color="Algorithm",
        barmode="group",
        labels={"Avg Runtime (s)": "Runtime (seconds)", "Scale": "Network Scale Tier"},
        color_discrete_map=colors,
    )
    fig_scale.update_layout(template="plotly_white", height=380)
    st.plotly_chart(fig_scale, width="stretch")

    st.info(
        "**Solvability Note on Large-Scale Network:** In the 24-corridor network, cumulative annual demand exceeds 1.5M TEU. When an operator fleet is restricted to only 24 vessels, servicing 24 routes while meeting weekly sailing frequency constraints is mathematically impossible. Scaling fleet availability proportionally (120 vessels) and connecting bunkering hubs renders the large-scale network solvable."
    )

with tab_pred:
    st.subheader("3. Fuel Prediction Regression Benchmark")
    st.markdown(
        "Summary of predictive modeling benchmark on 6,500 synthetic records evaluated using **repeated 10-fold cross-validation (20 paired folds)** with a **two-sided Wilcoxon signed-rank test**:"
    )

    p_metrics = p_data["metrics"]
    p_sig = p_data["significance_tests"]

    p_rows = []
    for k, v in p_metrics.items():
        p_rows.append(
            {
                "Predictor Model": k,
                "RMSE (tonnes)": v["rmse"],
                "MAE (tonnes)": v["mae"],
                "R² Score": v["r2"],
            }
        )
    st.dataframe(pd.DataFrame(p_rows), width="stretch")

    st.markdown("##### Two-Sided Paired Wilcoxon Signed-Rank Test Results (20 Folds)")
    w_rows = []
    for k, v in p_sig.items():
        w_rows.append(
            {
                "Comparison": f"Q-Predictor vs {k}",
                "Wilcoxon Statistic": v["statistic"],
                "p-value": f"{v['p_value']:.4f}",
                "Significant (p < 0.05)": "Yes" if v["is_significant"] else "No",
                "Direction": v.get("direction", "N/A"),
                "Interpretation": v["interpretation"],
            }
        )
    st.dataframe(pd.DataFrame(w_rows), width="stretch")

    st.caption(
        "**Physics Grounding:** Polynomial Ridge regression performs strongly because the synthetic fuel data generation model is governed by classical cubic speed law and deadweight displacement power laws, which are near-polynomial."
    )
