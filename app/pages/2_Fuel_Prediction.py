"""
Fuel Prediction Page - Baseline Models vs Quantum-Inspired Predictor & Interactive Voyage Calculator.
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
from src.prediction.evaluator import evaluate_prediction_models
from src.prediction.fuel_model import FuelModel

st.set_page_config(page_title="Fuel Prediction | Green Fleet", page_icon="📈", layout="wide")

st.title("📈 Fuel Consumption Prediction & Machine Learning")
st.markdown("Comparative evaluation of classical regression baselines vs the Quantum-Inspired Predictor with paired significance testing.")

st.info("**SYNTHETIC DATA DISCLAIMER:** All models are trained and evaluated on 6,500 synthetic voyage records.")

cfg = load_config()

# Controls
st.sidebar.header("Prediction Controls")
rerun_btn = st.sidebar.button("🔄 Re-run Prediction Benchmark", width="stretch", type="primary")

data_dir = PROJECT_ROOT / "data"
saved_pred_file = data_dir / "saved_prediction_results.pkl"


@st.cache_data(show_spinner="Evaluating prediction models and running paired Wilcoxon tests...")
def get_prediction_results(force_recompute: bool = False):
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
    pred_res = get_prediction_results(force_recompute=True)
else:
    pred_res = get_prediction_results(force_recompute=False)

metrics = pred_res["metrics"]
sig_tests = pred_res["significance_tests"]
preds_df = pred_res["test_predictions"]

# 1. Performance Overview Cards
st.subheader("1. Held-Out Test Set Performance Benchmark")

cols = st.columns(3)
for idx, (m_name, m_vals) in enumerate(metrics.items()):
    with cols[idx]:
        st.markdown(f"#### {m_name}")
        st.metric(label="RMSE", value=f"{m_vals['rmse']:.3f} t")
        st.metric(label="MAE", value=f"{m_vals['mae']:.3f} t")
        st.metric(label="R² Score", value=f"{m_vals['r2']:.4f}")

# Tabular comparison
rows = []
for m_name, m_vals in metrics.items():
    rows.append({
        "Model": m_name,
        "Test RMSE (tonnes)": m_vals["rmse"],
        "Test MAE (tonnes)": m_vals["mae"],
        "Test R² Score": m_vals["r2"],
    })
st.dataframe(pd.DataFrame(rows), width="stretch")

# 2. Paired Wilcoxon Significance Testing
st.markdown("---")
st.subheader("2. Repeated 10-Fold CV & Two-Sided Wilcoxon Significance Test")
st.markdown(
    """
    To verify whether performance differences across cross-validation folds are statistically meaningful,
    a repeated 10-fold cross validation (20 paired folds) with a **two-sided Wilcoxon signed-rank test** was conducted:
    """
)

sig_rows = []
for base_name, s_data in sig_tests.items():
    sig_rows.append({
        "Baseline Compared": base_name,
        "Baseline Fold RMSE": f"{s_data['mean_rmse_baseline']:.3f} t",
        "Q-Predictor Fold RMSE": f"{s_data['mean_rmse_qiea']:.3f} t",
        "Wilcoxon Statistic": s_data["statistic"],
        "p-value": f"{s_data['p_value']:.4f}",
        "Statistically Significant (p < 0.05)": "Yes" if s_data["is_significant"] else "No",
        "Direction": s_data.get("direction", "N/A"),
        "Interpretation": s_data["interpretation"],
    })
st.dataframe(pd.DataFrame(sig_rows), width="stretch")

st.info(
    "**Architectural Note on Hydrodynamic Data:** Polynomial Ridge regression closely matches or outperforms tree-based models on this benchmark because the synthetic data generation engine is grounded in classical naval architecture physics (cubic speed law $P \\propto V^3$ and Admiralty coefficients with deadweight displacement scaling), which are near-polynomial by formulation."
)

# 3. Visual Diagnostics
st.markdown("---")
st.subheader("3. Predictive Diagnostics & Convergence")

vis_col1, vis_col2 = st.columns(2)

with vis_col1:
    st.markdown("##### Predicted vs Actual Fuel Consumption")
    sample_df = preds_df.sample(min(400, len(preds_df)), random_state=42)
    fig_scatter = go.Figure()

    min_val = min(sample_df["actual"].min(), sample_df["Quantum-Inspired Predictor"].min())
    max_val = max(sample_df["actual"].max(), sample_df["Quantum-Inspired Predictor"].max())
    fig_scatter.add_trace(go.Scatter(
        x=[min_val, max_val], y=[min_val, max_val],
        mode="lines", name="Ideal Parity", line=dict(color="gray", dash="dash")
    ))

    fig_scatter.add_trace(go.Scatter(
        x=sample_df["actual"], y=sample_df["Quantum-Inspired Predictor"],
        mode="markers", name="Q-Predictor", marker=dict(color="#10b981", size=6, opacity=0.7)
    ))
    fig_scatter.add_trace(go.Scatter(
        x=sample_df["actual"], y=sample_df["Gradient Boosting (Default)"],
        mode="markers", name="Default GB", marker=dict(color="#6366f1", size=6, opacity=0.4)
    ))

    fig_scatter.update_layout(
        xaxis_title="Actual Fuel Burn (tonnes)",
        yaxis_title="Predicted Fuel Burn (tonnes)",
        template="plotly_white",
        height=380,
    )
    st.plotly_chart(fig_scatter, width="stretch")

with vis_col2:
    st.markdown("##### QIEA Optimization Convergence")
    st.markdown(
        f"**Selected Features:** `{', '.join(pred_res['qiea_selected_features'])}`  \n"
        f"**Tuned Hyperparameters:** `{pred_res['qiea_best_params']}`"
    )
    conv_curve = pred_res["qiea_convergence"]
    fig_conv = px.line(
        x=list(range(1, len(conv_curve) + 1)),
        y=conv_curve,
        markers=True,
        labels={"x": "QIEA Generation", "y": "Cross-Validation RMSE (t)"},
        title="QIEA Feature Selection & Hyperparameter Tuning",
    )
    fig_conv.update_traces(line_color="#2563eb", marker=dict(size=6))
    fig_conv.update_layout(template="plotly_white", height=320)
    st.plotly_chart(fig_conv, width="stretch")

# 4. Interactive Voyage Fuel Estimator Widget
st.markdown("---")
st.subheader("4. Interactive Voyage Fuel Estimator")
st.markdown("Estimate fuel consumption for custom voyage parameters using the unified `FuelModel` interface:")

calc_col1, calc_col2 = st.columns(2)

with calc_col1:
    selected_vessel = st.selectbox(
        "Vessel Class",
        options=list(cfg["vessel_types"].keys()),
        format_func=lambda x: cfg["vessel_types"][x]["name"],
    )
    v_info = cfg["vessel_types"][selected_vessel]

    speed_in = st.slider(
        "Cruising Speed (knots)",
        min_value=float(v_info["v_min_knots"]),
        max_value=float(v_info["v_max_knots"]),
        value=float(v_info["v_ref_knots"]),
        step=0.25,
    )

    load_in = st.slider(
        "Cargo Payload (tonnes)",
        min_value=1000.0,
        max_value=float(v_info["capacity_dwt"]),
        value=float(v_info["l_ref_tonnes"]),
        step=500.0,
    )

with calc_col2:
    dist_in = st.number_input("Voyage Distance (nautical miles)", min_value=50.0, max_value=3500.0, value=890.0, step=50.0)
    weather_in = st.slider("Adverse Weather Severity (0 = Calm, 1 = Gale)", min_value=0.0, max_value=1.0, value=0.30, step=0.05)

    pred_mode = st.radio(
        "Prediction Mode",
        options=["physics", "ml"],
        format_func=lambda x: "Analytical Physics Model (Cubic Speed & Displacement)" if x == "physics" else "Quantum-Tuned Machine Learning Model",
        horizontal=True,
    )

fm = FuelModel(
    config=cfg,
    trained_predictor=pred_res["trained_models"]["Quantum-Inspired Predictor"],
    feature_names=pred_res["feature_names"],
)

est_fuel = fm.predict(
    vessel_type=selected_vessel,
    speed_knots=speed_in,
    cargo_load_tonnes=load_in,
    distance_nm=dist_in,
    weather_severity=weather_in,
    mode=pred_mode,
)

transit_days = dist_in / (24.0 * max(0.1, speed_in))

res_col1, res_col2, res_col3 = st.columns(3)
res_col1.metric("Estimated Fuel Burn", f"{est_fuel:.2f} tonnes")
res_col2.metric("Sea Transit Duration", f"{transit_days:.2f} days ({transit_days * 24:.1f} hrs)")
res_col3.metric("Burn Rate", f"{est_fuel / max(0.01, transit_days):.2f} tonnes/day")

st.caption(
    "**Mode Tradeoff:** Analytical physics is deterministic, microsecond-fast, and physically consistent across any extrapolation. The ML model incorporates empirical wave resistance and hull biofouling interactions from synthetic maritime telemetry."
)
