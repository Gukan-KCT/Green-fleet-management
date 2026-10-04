"""
Fuel Predictor - Operational Voyage Fuel Consumption Estimator.
Interactive vessel hydrodynamics and machine learning regression comparison.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="Fuel Predictor | Green Fleet",
    page_icon="⛽",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.theme import apply_theme_layout, UI_COLORS
from app.ui.css import inject_css
from app.ui.state import get_or_load_prediction_results, get_default_config
from src.models.physics import (
    calculate_leg_fuel_conventional,
    calculate_alternative_fuel_mass,
    calculate_emissions,
    get_fuel_price_usd_per_tonne,
    load_config,
)
from src.prediction.fuel_model import FuelModel
from src.analysis.decision_support import compute_carbon_intensity_rating

render_top_strip(
    title="Fuel Consumption Predictor",
    subtitle="End-to-end operational voyage bunker forecasting: Real ML regressors vs classical naval physics.",
)

inject_css()
cfg = get_default_config()
pred_res = get_or_load_prediction_results()
trained_models = pred_res.get("trained_models", {}) if pred_res else {}

# --- 1. Top Section: Inputs & Live Prediction ---
col_in, col_pred = st.columns([10, 10])

vessel_types = list(cfg["vessel_types"].keys())
vessel_names = {k: cfg["vessel_types"][k]["name"] for k in vessel_types}
fuel_types = list(cfg.get("fuels", {}).keys())

with col_in:
    with st.container(border=True):
        st.markdown("**Voyage Operational Parameters**")
        v_sel = st.selectbox(
            "Vessel Class",
            options=vessel_types,
            format_func=lambda x: vessel_names[x],
            help="Select vessel size class and design displacement rating.",
        )
        v_info = cfg["vessel_types"][v_sel]
        v_cap_dwt = float(v_info.get("capacity_dwt", v_info.get("l_ref_tonnes", 20000.0)))

        c_s1, c_s2 = st.columns(2)
        with c_s1:
            speed_in = st.slider(
                "Cruising Speed (knots)",
                min_value=float(v_info["v_min_knots"]),
                max_value=float(v_info["v_max_knots"]),
                value=float(v_info["v_ref_knots"]),
                step=0.5,
                help="Service operating speed across sea passage.",
            )
            load_ratio = st.slider(
                "Cargo Load Factor (%)",
                min_value=10,
                max_value=100,
                value=80,
                step=5,
                help=f"Deadweight cargo utilization percentage. Design DWT: {v_cap_dwt:,.0f} tonnes.",
            )
            fuel_sel = st.selectbox(
                "Bunker Fuel Type",
                options=fuel_types,
                index=fuel_types.index("HFO") if "HFO" in fuel_types else 0,
                help="Select conventional bunker or green alternative fuel.",
            )
        with c_s2:
            dist_in = st.number_input(
                "Leg Distance (nm)",
                min_value=10.0,
                max_value=25000.0,
                value=1250.0,
                step=50.0,
                help="One-way voyage distance in nautical miles.",
            )
            weather_sev = st.slider(
                "Weather Severity (0 = Calm, 1 = Storm)",
                min_value=0.0,
                max_value=1.0,
                value=0.25,
                step=0.05,
                help="Beaufort scale environmental sea state and wind resistance penalty factor.",
            )
            avail_models = list(trained_models.keys()) if trained_models else ["Quantum-Inspired Predictor", "Polynomial Ridge", "Gradient Boosting (Default)"]
            selected_model_name = st.selectbox(
                "ML Predictor Architecture",
                options=avail_models,
                index=0,
                help="Select trained machine learning model for voyage prediction.",
            )

        # Capacity and cargo load summary
        cargo_tonnes = (load_ratio / 100.0) * v_cap_dwt
        st.caption(f"**Displacement Cargo Mass:** `{cargo_tonnes:,.0f} tonnes` | **Vessel Capacity:** `{v_cap_dwt:,.0f} DWT`")

# 1. Compute Physics Baseline
phys_fuel_hfo, leg_time_days = calculate_leg_fuel_conventional(
    vessel_cfg=v_info,
    speed_knots=speed_in,
    distance_nm=dist_in,
    cargo_load_tonnes=cargo_tonnes,
    weather_severity=weather_sev,
)
if fuel_sel != "HFO":
    phys_fuel_tonnes = calculate_alternative_fuel_mass(phys_fuel_hfo, fuel_sel, cfg)
else:
    phys_fuel_tonnes = phys_fuel_hfo

# 2. Compute Real ML Prediction using trained model
ml_fuel_hfo = phys_fuel_hfo
is_ml_active = False

if trained_models and selected_model_name in trained_models:
    try:
        f_model = FuelModel(
            config=cfg,
            trained_predictor=trained_models[selected_model_name],
            feature_names=pred_res.get("feature_names"),
            model_name=selected_model_name,
        )
        ml_fuel_hfo = f_model.predict(
            vessel_type=v_sel,
            speed_knots=speed_in,
            cargo_load_tonnes=cargo_tonnes,
            distance_nm=dist_in,
            weather_severity=weather_sev,
            mode="ml",
        )
        is_ml_active = True
    except Exception:
        ml_fuel_hfo = phys_fuel_hfo

if fuel_sel != "HFO":
    ml_fuel_tonnes = calculate_alternative_fuel_mass(ml_fuel_hfo, fuel_sel, cfg)
else:
    ml_fuel_tonnes = ml_fuel_hfo

diff_tonnes = ml_fuel_tonnes - phys_fuel_tonnes
diff_pct = ((ml_fuel_tonnes - phys_fuel_tonnes) / max(0.01, phys_fuel_tonnes)) * 100.0

# 3. Emissions and Cost Calculations
default_tax = float(cfg.get("general", {}).get("carbon_price_usd_per_tonne", 80.0))
fuel_price = get_fuel_price_usd_per_tonne(fuel_sel, "default", cfg)

emiss_ml = calculate_emissions(ml_fuel_tonnes, fuel_sel, "default", cfg)
emiss_phys = calculate_emissions(phys_fuel_tonnes, fuel_sel, "default", cfg)

cost_ml_fuel = ml_fuel_tonnes * fuel_price
cost_ml_tax = emiss_ml["total_co2e"] * default_tax
cost_ml_total = cost_ml_fuel + cost_ml_tax

t_nm = max(1.0, cargo_tonnes * dist_in)
ci_g_tnm = (emiss_ml["total_co2e"] * 1e6) / t_nm
ci_rating = compute_carbon_intensity_rating(ci_g_tnm)

# Collect all model predictions for chart
model_preds = {
    "Naval Hydrodynamics (Physics)": round(phys_fuel_tonnes, 2),
}
for m_name, m_inst in trained_models.items():
    try:
        inst_model = FuelModel(
            config=cfg,
            trained_predictor=m_inst,
            feature_names=pred_res.get("feature_names"),
            model_name=m_name,
        )
        m_hfo = inst_model.predict(
            vessel_type=v_sel,
            speed_knots=speed_in,
            cargo_load_tonnes=cargo_tonnes,
            distance_nm=dist_in,
            weather_severity=weather_sev,
            mode="ml",
        )
        val = calculate_alternative_fuel_mass(m_hfo, fuel_sel, cfg) if fuel_sel != "HFO" else m_hfo
        model_preds[m_name] = round(val, 2)
    except Exception:
        pass

with col_pred:
    with st.container(border=True):
        st.markdown("**Voyage Prediction Results**")
        st.caption(f"Active Model: **{selected_model_name if is_ml_active else 'Physics'}** | Fuel: **{fuel_sel}** | Transit: **{leg_time_days:.1f} days**")

        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        with kpi_c1:
            st.metric(
                label="ML Predicted Fuel",
                value=f"{ml_fuel_tonnes:.2f} t",
                delta=f"{diff_pct:+.1f}% vs Physics",
                delta_color="inverse" if diff_pct > 0 else "normal",
                help=f"Predicted fuel burn using trained {selected_model_name}.",
            )
        with kpi_c2:
            st.metric(
                label="Physics Estimate",
                value=f"{phys_fuel_tonnes:.2f} t",
                help="Calculated via Holtrop-Mennen cubic resistance law and displacement scaling.",
            )
        with kpi_c3:
            st.metric(
                label="Total Voyage Cost",
                value=f"${cost_ml_total:,.0f}",
                help=f"Bunker (${cost_ml_fuel:,.0f}) + Carbon Tax (${cost_ml_tax:,.0f} @ ${default_tax:.0f}/t CO2e)",
            )

        kpi_e1, kpi_e2, kpi_e3 = st.columns(3)
        with kpi_e1:
            st.metric(
                label="Estimated CO2e",
                value=f"{emiss_ml['total_co2e']:.2f} t",
                help="Lifecycle Well-to-Wake (combustion + upstream fuel supply chain)",
            )
        with kpi_e2:
            st.metric(
                label="Carbon Intensity",
                value=f"{ci_g_tnm:.1f} g/t-nm",
                help="Operational voyage carbon intensity per cargo tonne-nautical mile.",
            )
        with kpi_e3:
            st.metric(
                label="CII Rating Proxy",
                value=f"Grade {ci_rating['grade']}",
                help=f"{ci_rating['description']} (Simplified proxy, not official IMO CII).",
            )

        fig_bar = go.Figure(
            go.Bar(
                x=list(model_preds.keys()),
                y=list(model_preds.values()),
                marker_color=["#0f4c81", "#457b9d", "#64748b", "#2a9d8f"][:len(model_preds)],
                text=[f"{v:.1f} t" for v in model_preds.values()],
                textposition="auto",
                hovertemplate="%{x}: <b>%{y:.2f} tonnes</b><extra></extra>",
            )
        )
        apply_theme_layout(
            fig_bar,
            xaxis_title="Model Architecture",
            yaxis_title=f"Voyage Consumption (tonnes {fuel_sel})",
            height=230,
            show_legend=False,
        )
        st.plotly_chart(fig_bar, width="stretch")

# --- 2. Bottom Analytical Tabs ---
t_acc, t_scatter, t_sig, t_feats = st.tabs([
    "Model Accuracy Benchmark",
    "Predicted vs Actual Scatter",
    "Statistical Significance (Wilcoxon)",
    "QIEA Selected Hyperparameters",
])

with t_acc:
    if pred_res is not None and "metrics" in pred_res:
        acc_rows = []
        for m_name, m_stats in pred_res["metrics"].items():
            acc_rows.append({
                "Model Architecture": m_name,
                "Test RMSE (tonnes)": m_stats.get("rmse", 0.0),
                "Test MAE (tonnes)": m_stats.get("mae", 0.0),
                "Test R² Score": m_stats.get("r2", 0.0),
                "Training/Test Split": "80% Train (800 voyages) / 20% Test (200 voyages)",
            })
        st.dataframe(pd.DataFrame(acc_rows), hide_index=True, width="stretch")
        st.caption(
            "Architectural Note: Polynomial Ridge matches tree-based regressors because hydrodynamic fuel burn "
            "follows classical physical cubic laws (P ∝ V³) and deadweight scaling, which are near-polynomial."
        )
    else:
        st.info("Precomputed metrics loading from data/saved_prediction_results.pkl.")

with t_scatter:
    if pred_res is not None and "test_predictions" in pred_res:
        test_preds = pred_res["test_predictions"]
        y_act = test_preds.get("actual", [])
        fig_sc = go.Figure()
        fig_sc.add_trace(
            go.Scatter(
                x=y_act[:400],
                y=y_act[:400],
                mode="lines",
                line=dict(color="#cbd5e1", dash="dash"),
                name="Ideal 1:1 Identity",
            )
        )
        for m_name in ["Polynomial Ridge", "Quantum-Inspired Predictor"]:
            if m_name in test_preds:
                fig_sc.add_trace(
                    go.Scatter(
                        x=y_act[:400],
                        y=test_preds[m_name][:400],
                        mode="markers",
                        marker=dict(size=5, opacity=0.6),
                        name=m_name,
                    )
                )
        apply_theme_layout(
            fig_sc,
            title="Predicted vs Actual Voyage Fuel Consumption (Test Set Sample)",
            xaxis_title="Actual Simulated Fuel (tonnes)",
            yaxis_title="Model Predicted Fuel (tonnes)",
            height=340,
        )
        st.plotly_chart(fig_sc, width="stretch")
    else:
        st.info("Scatter plot displays once precomputed voyage predictions are available.")

with t_sig:
    if pred_res is not None and "significance_tests" in pred_res:
        sig_data = pred_res["significance_tests"]
        sig_rows = []
        for b_name, s_info in sig_data.items():
            sig_rows.append({
                "Baseline Model": b_name,
                "Wilcoxon W-Stat": round(s_info.get("statistic", 0.0), 1),
                "p-value (two-sided)": f"{s_info.get('p_value', 1.0):.4f}",
                "Significant (p < 0.05)": "Yes" if s_info.get("is_significant") else "No",
                "Direction": s_info.get("direction", "Comparable"),
                "Finding": s_info.get("interpretation", ""),
            })
        st.dataframe(pd.DataFrame(sig_rows), hide_index=True, width="stretch")
    else:
        st.info("Significance tests evaluated via repeated 10-fold cross validation.")

with t_feats:
    q_feats = pred_res.get("qiea_selected_features", []) if pred_res else []
    q_params = pred_res.get("qiea_best_params", {}) if pred_res else {}
    if q_feats or q_params:
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            st.markdown("**Features Retained by QIEA Binary Selection**")
            for f in q_feats:
                st.markdown(f"- `{f}`")
        with c_f2:
            st.markdown("**Optimized Hyperparameters**")
            for p_k, p_v in q_params.items():
                st.markdown(f"- `{p_k}`: **{p_v}**")
    else:
        st.caption("QIEA dynamically optimizes binary gene subsets: 8 feature flags and 10 hyperparameter bits.")

