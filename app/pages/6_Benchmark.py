"""
Benchmark - Algorithmic Optimization & Scalability Suite.
Rigorous multi-seed comparison of QIEA, Genetic Algorithm, PSO, Hill Climbing, and Random Search.
Includes Q-Bit Superposition Visualizer, Robustness Multi-Seed Analysis, and Ablation Study.
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
from app.ui.charts import build_qbit_probabilities_heatmap
from app.ui.css import inject_css
from app.ui.state import (
    get_or_load_benchmark_results,
    get_or_load_scalability_results,
    get_or_load_q_history,
    get_or_load_robustness,
    get_default_config,
    check_artifact_staleness,
)
from src.analysis.benchmark import (
    run_benchmark_suite,
    run_scalability_analysis,
    DEFAULT_BENCHMARK_SEEDS,
)
from src.optimization.problem import FleetOptimizationProblem

render_top_strip(
    title="Algorithmic Optimization Benchmark & Robustness",
    subtitle="Comparative convergence, solution quality, and scalability across 10 random seeds (20,000 evals/run).",
    demo_only=True,
)

inject_css()

cfg = get_default_config()

if check_artifact_staleness("saved_benchmark_results.pkl"):
    st.warning("Saved benchmark results are out of date, press Re-run to update.", icon="⚠️")

# --- 1. Load Data & Controls ---
c_head, c_btn = st.columns([8, 2])
with c_head:
    st.caption("Benchmark evaluates 5 algorithms on identical budgets without hardcoded bias: QIEA, Memetic GA, Continuous-to-Binary PSO, Hill-Climb Search, and Random Search.")
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

# --- 2. Top-Level Metric Leaders & Tabs ---
b_tab1, b_tab2, b_tab3, b_tab4 = st.tabs([
    "Benchmark Comparison",
    "Quantum-Inspired Mechanism Visualizer",
    "Optimizer Robustness (10 Seeds)",
    "Scalability Analysis",
])

with b_tab1:
    st.markdown("### Empirical Performance Summary & Metric Leaders")

    w_fit_row = df_summary.sort_values(by="Best Fitness", ascending=True).iloc[0]
    w_mean_row = df_summary.sort_values(by="Mean Fitness", ascending=True).iloc[0]
    w_feas_row = df_summary.sort_values(by="Feasibility Rate (%)", ascending=False).iloc[0]
    w_speed_row = df_summary.sort_values(by="Avg Runtime (s)", ascending=True).iloc[0]

    leader_cols = st.columns(4)
    with leader_cols[0]:
        st.markdown(
            f"""<div style="border-top:3px solid #0f4c81; background:#fff; border:1px solid #e2e8f0;
            border-radius:8px; padding:0.75rem 1rem; box-shadow:0 1px 3px rgba(15,76,129,.08);">
            <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Lowest Best Fitness</div>
            <div style="font-size:17px;font-weight:700;color:#1e293b;margin:3px 0;">{w_fit_row['Algorithm']}</div>
            <div style="font-size:12px;color:#0f4c81;font-weight:600;">{w_fit_row['Best Fitness']:.4f}</div></div>""",
            unsafe_allow_html=True,
        )
    with leader_cols[1]:
        st.markdown(
            f"""<div style="border-top:3px solid #2a9d8f; background:#fff; border:1px solid #e2e8f0;
            border-radius:8px; padding:0.75rem 1rem; box-shadow:0 1px 3px rgba(15,76,129,.08);">
            <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Lowest Mean Fitness</div>
            <div style="font-size:17px;font-weight:700;color:#1e293b;margin:3px 0;">{w_mean_row['Algorithm']}</div>
            <div style="font-size:12px;color:#2a9d8f;font-weight:600;">{w_mean_row['Mean Fitness']:.4f}</div></div>""",
            unsafe_allow_html=True,
        )
    with leader_cols[2]:
        st.markdown(
            f"""<div style="border-top:3px solid #0f4c81; background:#fff; border:1px solid #e2e8f0;
            border-radius:8px; padding:0.75rem 1rem; box-shadow:0 1px 3px rgba(15,76,129,.08);">
            <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Highest Feasibility</div>
            <div style="font-size:17px;font-weight:700;color:#1e293b;margin:3px 0;">{w_feas_row['Algorithm']}</div>
            <div style="font-size:12px;color:#0f4c81;font-weight:600;">{w_feas_row['Feasibility Rate (%)']:.1f}%</div></div>""",
            unsafe_allow_html=True,
        )
    with leader_cols[3]:
        st.markdown(
            f"""<div style="border-top:3px solid #2a9d8f; background:#fff; border:1px solid #e2e8f0;
            border-radius:8px; padding:0.75rem 1rem; box-shadow:0 1px 3px rgba(15,76,129,.08);">
            <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Fastest Execution</div>
            <div style="font-size:17px;font-weight:700;color:#1e293b;margin:3px 0;">{w_speed_row['Algorithm']}</div>
            <div style="font-size:12px;color:#2a9d8f;font-weight:600;">{w_speed_row['Avg Runtime (s)']:.2f}s</div></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(
        df_summary,
        column_config={
            "Best Fitness": st.column_config.NumberColumn(format="%.4f"),
            "Mean Fitness": st.column_config.NumberColumn(format="%.4f"),
            "Std Fitness": st.column_config.NumberColumn(format="%.4f"),
            "Feasibility Rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg Runtime (s)": st.column_config.NumberColumn(format="%.3fs"),
            "Avg Evaluations": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        width="stretch",
    )

    # Narrative Findings Box
    with st.container(border=True):
        st.markdown("**Empirical Findings & Data-Driven Narrative**")
        st.write(bench_data.get("narrative", "Evaluating empirical benchmark runs..."))

    # Convergence & Box Plots
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        with st.container(border=True):
            st.markdown("**Mean Convergence Trajectories across 10 Seeds**")
            fig_conv = go.Figure()
            for alg, conv_arr in mean_conv.items():
                if "Random" in alg:
                    continue
                color = ALGO_COLORS.get(alg, "#0f4c81")
                fig_conv.add_trace(
                    go.Scatter(
                        x=list(range(1, len(conv_arr) + 1)),
                        y=conv_arr,
                        mode="lines",
                        name=alg,
                        line=dict(color=color, width=2.2),
                    )
                )
            apply_theme_layout(
                fig_conv,
                xaxis_title="Generation",
                yaxis_title="Mean Objective Score",
                height=300,
                show_legend=True,
            )
            st.plotly_chart(fig_conv, width="stretch")

    with col_c2:
        with st.container(border=True):
            st.markdown("**Solution Quality Distribution (Box Plots)**")
            fig_box = go.Figure()
            if isinstance(raw_runs, dict):
                for alg, runs_list in raw_runs.items():
                    if "Random" in alg:
                        continue
                    fits = [r.get("fitness", 0.0) for r in runs_list]
                    fig_box.add_trace(
                        go.Box(
                            y=fits,
                            name=alg,
                            marker_color=ALGO_COLORS.get(alg, "#0f4c81"),
                            boxpoints="all",
                            jitter=0.3,
                        )
                    )
            apply_theme_layout(
                fig_box,
                xaxis_title="Algorithm",
                yaxis_title="Best Fitness (Lower is Better)",
                height=300,
                show_legend=False,
            )
            st.plotly_chart(fig_box, width="stretch")

with b_tab2:
    st.markdown("### Quantum-Inspired Probabilistic Superposition Visualizer")
    st.caption("Inspects the dynamic evolution of Q-bit observation probabilities $\\sin^2(\\theta_i)$ across generations as rotation gates converge toward elite binary alleles.")

    q_data = get_or_load_q_history()
    if q_data is not None and "q_prob_history" in q_data:
        history = q_data["q_prob_history"]
        n_gens = len(history)

        fig_heat = build_qbit_probabilities_heatmap(history, max_bits=35)
        st.plotly_chart(fig_heat, width="stretch")

        gen_slider = st.slider("Select Generation to Inspect Q-Bit Superposition State", 1, n_gens, n_gens // 2)
        cur_probs = np.array(history[gen_slider - 1])
        collapsed_zeros = int(np.sum(cur_probs < 0.05))
        collapsed_ones = int(np.sum(cur_probs > 0.95))
        superposition_bits = len(cur_probs) - collapsed_zeros - collapsed_ones

        col_q1, col_q2, col_q3 = st.columns(3)
        with col_q1:
            st.metric("Bits Collapsed to 0 (P < 0.05)", f"{collapsed_zeros} / {len(cur_probs)}")
        with col_q2:
            st.metric("Bits in Active Superposition", f"{superposition_bits} / {len(cur_probs)}")
        with col_q3:
            st.metric("Bits Collapsed to 1 (P > 0.95)", f"{collapsed_ones} / {len(cur_probs)}")

        st.info("ℹ️ **Scientific Caption:** *Classical simulation on standard CPU. Probabilistic angular representation simulates quantum-like superposition and rotation gates; no quantum hardware or quantum advantage is claimed.*")
    else:
        st.info("Q-bit history is being precomputed by scripts/run_experiments.py...")

with b_tab3:
    st.markdown("### Optimizer Multi-Seed Robustness & Route Stability (K = 10 Seeds)")
    st.caption("Verifies whether independent random seeds produce consistent vessel and fuel allocations across shipping corridors.")

    robust_data = get_or_load_robustness()
    if robust_data is not None:
        df_rob = robust_data["route_robustness_df"]
        kpis = robust_data["kpi_stats"]
        sens = robust_data.get("sensitive_routes", [])

        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.metric("Annual Operating Cost", f"${kpis['cost_mean_m']:.2f}M", f"± ${kpis['cost_std_m']:.3f}M std")
        with col_r2:
            st.metric("Lifecycle Emissions", f"{kpis['co2_mean_kt']:.2f} kt", f"± {kpis['co2_std_kt']:.3f} kt std")
        with col_r3:
            st.metric("Bunker Fuel Consumption", f"{kpis['fuel_mean_t']:,.1f} t", f"± {kpis['fuel_std_t']:.1f} t std")

        st.dataframe(
            df_rob,
            column_config={
                "Consensus (%)": st.column_config.ProgressColumn("Seed Consensus", min_value=0, max_value=100, format="%.1f%%"),
                "Status": st.column_config.TextColumn("Stability Status"),
            },
            hide_index=True,
            width="stretch",
        )

        if sens:
            st.warning(f"**Sensitive Corridors Detected:** Corridor(s) **{', '.join(sens)}** exhibit variability under alternative random seeds due to competing near-optimal fleet configurations.")
        else:
            st.success("**High Fleet Robustness:** All corridors achieved >= 80% consensus across 10 independent optimizer runs.")
    else:
        st.info("Robustness analysis is precomputing across 10 seeds...")

with b_tab4:
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
