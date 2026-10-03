"""
Benchmark - Algorithmic Optimization & Scalability Suite.
Rigorous multi-seed comparison of QIEA, Genetic Algorithm, PSO, and Random Search.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Benchmark | Green Fleet",
    page_icon="⚡",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, ALGO_COLORS, UI_COLORS
from app.ui.state import (
    get_or_load_benchmark_results,
    get_or_load_scalability_results,
    get_default_config,
)
from src.analysis.benchmark import (
    run_benchmark_suite,
    run_scalability_analysis,
    DEFAULT_BENCHMARK_SEEDS,
)
from src.optimization.problem import FleetOptimizationProblem

render_top_strip(
    title="Algorithmic Optimization Benchmark",
    subtitle="Comparative convergence, solution quality, and scalability across 10 random seeds (20,000 evals/run).",
)

cfg = get_default_config()

# --- 1. Load Data & Controls ---
c_head, c_btn = st.columns([8, 2])
with c_head:
    st.caption("Benchmark evaluates 4 algorithms on identical budgets without hardcoded bias: QIEA, Canonical GA, Continuous-to-Binary PSO, and Random Search.")
with c_btn:
    rerun_clicked = st.button("Re-run benchmark", width="stretch")

if rerun_clicked:
    with st.spinner("Executing full 10-seed benchmark suite (20,000 evaluations per algorithm)..."):
        prob_med = FleetOptimizationProblem(config=cfg)
        bench_data = run_benchmark_suite(
            problem=prob_med,
            seeds=DEFAULT_BENCHMARK_SEEDS,
            pop_size=50,
            generations=400,
        )
        st.session_state["benchmark_results"] = bench_data
else:
    bench_data = get_or_load_benchmark_results()

if bench_data is None:
    st.info("Loading precomputed benchmark results from data/saved_benchmark_results.pkl...")
    st.stop()

df_summary = bench_data["summary"]
raw_runs = bench_data.get("raw_runs", [])
mean_conv = bench_data.get("mean_convergence", {})

# --- 2. Winner Per Metric Table (Computed Strictly from Data) ---
st.markdown("### Empirical Performance Summary & Metric Leaders")

w_fit_row = df_summary.sort_values(by="Best Fitness", ascending=True).iloc[0]
w_mean_row = df_summary.sort_values(by="Mean Fitness", ascending=True).iloc[0]
w_feas_row = df_summary.sort_values(by="Feasibility Rate (%)", ascending=False).iloc[0]
w_speed_row = df_summary.sort_values(by="Avg Runtime (s)", ascending=True).iloc[0]

leader_cols = st.columns(4)
with leader_cols[0]:
    with st.container(border=True):
        st.caption("Lowest Best Fitness")
        st.markdown(f"**{w_fit_row['Algorithm']}**")
        st.markdown(f"Score: **{w_fit_row['Best Fitness']:.4f}**")
with leader_cols[1]:
    with st.container(border=True):
        st.caption("Lowest Mean Fitness")
        st.markdown(f"**{w_mean_row['Algorithm']}**")
        st.markdown(f"Mean: **{w_mean_row['Mean Fitness']:.4f}**")
with leader_cols[2]:
    with st.container(border=True):
        st.caption("Highest Feasibility")
        st.markdown(f"**{w_feas_row['Algorithm']}**")
        st.markdown(f"Rate: **{w_feas_row['Feasibility Rate (%)']:.1f}%**")
with leader_cols[3]:
    with st.container(border=True):
        st.caption("Fastest Execution")
        st.markdown(f"**{w_speed_row['Algorithm']}**")
        st.markdown(f"Runtime: **{w_speed_row['Avg Runtime (s)']:.2f}s**")

st.dataframe(
    df_summary,
    column_config={
        "Algorithm": st.column_config.TextColumn("Algorithm"),
        "Best Fitness": st.column_config.NumberColumn("Best Fitness (Min)", format="%.4f"),
        "Mean Fitness": st.column_config.NumberColumn("Mean Fitness", format="%.4f"),
        "Std Fitness": st.column_config.NumberColumn("Std Dev", format="%.4f"),
        "Feasibility Rate (%)": st.column_config.NumberColumn("Feasibility", format="%.1f%%"),
        "Avg Runtime (s)": st.column_config.NumberColumn("Avg Runtime", format="%.2fs"),
        "Avg Evaluations": st.column_config.NumberColumn("Evaluations", format="%d"),
    },
    hide_index=True,
    width="stretch",
)

# --- 3. Convergence & Box Plot Charts ---
col_c1, col_c2 = st.columns(2)

with col_c1:
    with st.container(border=True):
        st.markdown("**Mean Convergence Trajectories across 10 Seeds**")
        st.caption("Tracking penalized objective value over 400 generations (20,000 function evaluations).")
        fig_conv = go.Figure()
        for alg, conv_arr in mean_conv.items():
            if "Random" in alg:
                continue  # Skip unguided random search on scale
            color = ALGO_COLORS.get(alg, "#0f4c81")
            x_vals = list(range(1, len(conv_arr) + 1))
            fig_conv.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=conv_arr,
                    mode="lines",
                    name=alg,
                    line=dict(color=color, width=2.2),
                    hovertemplate=f"<b>{alg}</b><br>Gen %{{x}}: Fitness %{{y:.4f}}<extra></extra>",
                )
            )
        apply_theme_layout(
            fig_conv,
            xaxis_title="Generation",
            yaxis_title="Mean Penalized Objective (Lower is Better)",
            height=320,
            show_legend=True,
        )
        st.plotly_chart(fig_conv, width="stretch")

with col_c2:
    with st.container(border=True):
        st.markdown("**Solution Quality Distribution (Box Plots across 10 Seeds)**")
        st.caption("Distribution of best observed objective fitness values.")
        fig_box = go.Figure()
        if isinstance(raw_runs, dict):
            for alg, runs_list in raw_runs.items():
                if "Random" in alg:
                    continue  # Skip random search outlier scale
                fits = [r.get("fitness", 0.0) for r in runs_list]
                fig_box.add_trace(
                    go.Box(
                        y=fits,
                        name=alg,
                        marker_color=ALGO_COLORS.get(alg, "#0f4c81"),
                        boxpoints="all",
                        jitter=0.3,
                        pointpos=-1.8,
                    )
                )
        apply_theme_layout(
            fig_box,
            xaxis_title="Algorithm",
            yaxis_title="Best Fitness (Lower is Better)",
            height=320,
            show_legend=False,
        )
        st.plotly_chart(fig_box, width="stretch")

# --- 4. Multi-Scale Scalability Analysis ---
st.markdown("### Multi-Scale Network Scalability (Small, Medium, Large)")
st.caption("Evaluated across Small (L=39 bits, 3 routes), Medium (L=101 bits, 5 routes), and Large (L=462 bits, 24 routes).")

scale_df = get_or_load_scalability_results()

if scale_df is not None:
    col_sc1, col_sc2 = st.columns([11, 9])
    with col_sc1:
        with st.container(border=True):
            st.markdown("**Mean Runtime Scaling across Decision Dimension (L)**")
            fig_sc = go.Figure()
            for alg in scale_df["Algorithm"].unique():
                sub = scale_df[scale_df["Algorithm"] == alg].sort_values(by="Decision Bits (L)")
                fig_sc.add_trace(
                    go.Scatter(
                        x=sub["Decision Bits (L)"],
                        y=sub["Avg Runtime (s)"],
                        mode="lines+markers",
                        name=alg,
                        line=dict(color=ALGO_COLORS.get(alg, "#0f4c81"), width=2),
                        marker=dict(size=8),
                    )
                )
            apply_theme_layout(
                fig_sc,
                xaxis_title="Chromosome Decision Bits (L)",
                yaxis_title="Execution Runtime (seconds)",
                height=280,
                show_legend=True,
            )
            st.plotly_chart(fig_sc, width="stretch")

    with col_sc2:
        with st.container(border=True):
            st.markdown("**Scalability Quality Matrix**")
            st.dataframe(
                scale_df[["Scale", "Decision Bits (L)", "Algorithm", "Mean Fitness", "Feasibility Rate (%)", "Avg Runtime (s)"]],
                column_config={
                    "Decision Bits (L)": st.column_config.NumberColumn(format="%d bits"),
                    "Mean Fitness": st.column_config.NumberColumn(format="%.2f"),
                    "Feasibility Rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Avg Runtime (s)": st.column_config.NumberColumn(format="%.2fs"),
                },
                hide_index=True,
                width="stretch",
            )
else:
    st.info("Scalability benchmark is precomputing across Small (L=39), Medium (L=101), and Large (L=462) networks.")

# Raw Runs Table in Expander
with st.expander("Full Seed-by-Seed Raw Experimental Runs", expanded=False):
    if raw_runs:
        flat_list = []
        if isinstance(raw_runs, dict):
            for alg, r_list in raw_runs.items():
                for r in r_list:
                    item = dict(r)
                    item["Algorithm"] = alg
                    flat_list.append(item)
        else:
            flat_list = raw_runs
        st.dataframe(pd.DataFrame(flat_list), hide_index=True, width="stretch")
