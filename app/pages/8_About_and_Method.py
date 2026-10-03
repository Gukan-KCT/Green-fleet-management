"""
About & Method - Mathematical Formulation, Naval Architecture, and Algorithmic Specifications.
Comprehensive technical documentation, parameter registry, and methodology disclosures.
"""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="About & Method | Green Fleet",
    page_icon="📖",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import render_top_strip
from app.ui.css import inject_css
from app.ui.state import get_default_config

render_top_strip(
    title="Methodology, Physics & Algorithmic Foundations",
    subtitle="Mathematical formulations, naval architecture resistance laws, and algorithmic derivations.",
)


inject_css()
cfg = get_default_config()

# --- 1. Problem Formulation ---
with st.expander("1. Multi-Objective Fleet Optimization Problem Formulation", expanded=True):
    st.markdown(
        """
        The platform formulates fleet deployment as a high-dimensional combinatorial discrete optimization problem.
        The objective is to minimize a normalized composite scalar fitness function combining three competing operational priorities:
        """
    )
    st.latex(
        r"F(\mathbf{x}) = w_f \cdot \frac{f_{\text{fuel}}(\mathbf{x})}{\mathcal{N}_{\text{fuel}}} + "
        r"w_c \cdot \frac{f_{\text{cost}}(\mathbf{x})}{\mathcal{N}_{\text{cost}}} + "
        r"w_e \cdot \frac{f_{\text{emiss}}(\mathbf{x})}{\mathcal{N}_{\text{emiss}}} + "
        r"\Pi(\mathbf{x})"
    )
    st.markdown(
        """
        where:
        - $\mathbf{x} \in \{0, 1\}^L$ is the binary decision bitstring.
        - $w_f, w_c, w_e \ge 0$ are user-specified objective weights satisfying $w_f + w_c + w_e = 1$.
        - $\mathcal{N}_{\text{fuel}}, \mathcal{N}_{\text{cost}}, \mathcal{N}_{\text{emiss}}$ are dimensional normalization constants.
        - $\Pi(\mathbf{x}) = \sum_k \lambda_k \cdot \max(0, g_k(\mathbf{x}))$ is the exterior penalty function penalizing constraint violations.
        """
    )

# --- 2. Naval Architecture Physics Formulas ---
with st.expander("2. Naval Architecture Hydrodynamics & Fuel Consumption Laws", expanded=False):
    st.markdown("**Single Voyage Transit Leg Fuel Burn Formula:**")
    st.latex(
        r"F_{\text{leg}} = F_{\text{daily}}(V) \times \Phi_{\text{load}}(L) \times \Phi_{\text{weather}}(W) \times T_{\text{transit}}(d, V)"
    )
    st.markdown(
        """
        1. **Propulsion Power Cubic Law:** $F_{\text{daily}}(V) = F_{\text{ref}} \left(\frac{V}{V_{\text{ref}}}\right)^3$
        2. **Admiralty Displacement Scaling:** $\Phi_{\text{load}}(L) = \left(\frac{\Delta_{\text{lightship}} + L}{\Delta_{\text{lightship}} + L_{\text{ref}}}\right)^{2/3}$
        3. **Weather Resistance Penalty:** $\Phi_{\text{weather}}(W) = 1 + k_w \cdot W$ (where $k_w = 0.35$, $W \in [0, 1]$)
        4. **Transit Duration:** $T_{\text{transit}} = \frac{d}{24 \cdot V}$ (days)
        """
    )
    st.markdown("**Alternative Marine Fuel Energy Equivalence:**")
    st.latex(
        r"M_{\text{alt}} = M_{\text{HFO}} \times \left(\frac{\text{LHV}_{\text{HFO}}}{\text{LHV}_{\text{alt}}}\right) \times \frac{1}{\eta_{\text{engine, alt}}}"
    )
    st.markdown("**Transport Work & Carbon Intensity Proxy (IMO CII):**")
    st.latex(
        r"W_{\text{transport}} = \sum_{r} \min\left(\text{Cap}_r, \text{Demand}_r\right) \times d_r \quad (\text{tonne-nm})"
    )
    st.latex(
        r"\text{CI} = \frac{\text{Total Emissions } (\text{g } \text{CO}_2\text{e})}{W_{\text{transport}}} \quad (\text{g/t-nm})"
    )

# --- 3. Quantum-Inspired Evolutionary Algorithm (QIEA) ---
with st.expander("3. Quantum-Inspired Evolutionary Algorithm (QIEA) Derivation", expanded=False):
    st.markdown(
        """
        QIEA is a **classical probabilistic meta-heuristic** running on standard CPUs that utilizes concepts analogous to quantum superposition and state rotation.
        """
    )
    st.markdown("**Q-bit Angular Parameterization:**")
    st.latex(
        r"|q_j\rangle = \cos(\theta_j)|0\rangle + \sin(\theta_j)|1\rangle, \quad \theta_j \in [0, \pi/2]"
    )
    st.markdown(
        """
        The probability of observing bit $x_j = 1$ is $P(x_j = 1) = \sin^2(\theta_j)$.
        At generation $t=0$, setting $\theta_j = \pi/4$ yields $P(1) = P(0) = 0.50$, representing an equal superposition of all $2^L$ configurations.
        """
    )
    st.markdown("**Directional Quantum Rotation Gate:**")
    st.latex(
        r"\theta_{i, j}^{(t+1)} = \theta_{i, j}^{(t)} + \Delta\theta_{i, j}"
    )
    st.markdown(
        """
        where $\Delta\theta_{i, j} = \pm 0.05 \text{ rad} \approx 2.86^\circ$ directs the phase angle toward the corresponding bit of the current global best solution $\mathbf{b}^*$.
        """
    )

# --- 4. Constraints & Mathematical Penalties ---
with st.expander("4. Regulatory & Operational Constraints", expanded=False):
    st.markdown(
        """
        1. **Cargo Demand Coverage:** For each corridor $r$, annual supplied capacity must meet or exceed annual demand:
           $$\sum_{o} n_{o, r} \cdot \text{Trips}_{o, r} \cdot \text{Capacity}_o \ge \text{Demand}_r$$
        2. **Commercial Service Frequency:** Minimum sailing frequency must be satisfied:
           $$\text{Freq}_r \ge \text{MinFrequency}_r \quad (\text{sailings/week})$$
        3. **Operator Fleet Availability:** Total deployed vessels cannot exceed company inventory:
           $$\sum_r n_{o, r} \le \text{Available}_v \quad \forall v \in \text{VesselTypes}$$
        4. **Cruising Speed Envelopes:** $V_{\min}(v) \le V_r \le \min(V_{\max}(v), V_{\text{cap}}(r))$
        5. **Carbon Intensity Cap:** $\text{CI} \le \text{CI}_{\text{cap}}$ (e.g. 18.0 g/t-nm)
        """
    )

# --- 5. System Parameter Registry ---
with st.expander("5. System Configuration & Techno-Economic Parameter Registry", expanded=False):
    st.markdown("**Vessel Fleet Archetypes:**")
    v_rows = []
    for k, v in cfg["vessel_types"].items():
        v_rows.append({
            "Key": k,
            "Name": v["name"],
            "Capacity (TEU)": v["capacity_teu"],
            "Deadweight (DWT)": v["capacity_dwt"],
            "Speed Range": f"{v['v_min_knots']} - {v['v_max_knots']} kn",
            "Ref Fuel Burn": f"{v['f_ref_tonnes_day']} t/day",
            "Daily Charter": f"${v['daily_charter_usd']:,}",
            "Available Fleet": v["fleet_available"],
        })
    st.dataframe(pd.DataFrame(v_rows), hide_index=True, width="stretch")

    st.markdown("**Marine Fuel Lifecycle Factors & Densities:**")
    f_rows = []
    for k, f in cfg["fuels"].items():
        f_rows.append({
            "Fuel": k,
            "Name": f["name"],
            "LHV (MJ/kg)": f["lhv_mj_kg"],
            "TtW EF (t CO2/t)": f["ef_tank_to_wake"],
            "Capacity Penalty": f"{f.get('capacity_penalty_pct', 0.0)}%",
            "Pathways": ", ".join(f.get("pathways", ["fossil"])),
        })
    st.dataframe(pd.DataFrame(f_rows), hide_index=True, width="stretch")

# --- 6. Disclaimers & Assumptions ---
with st.expander("6. Methodology Disclaimers & Scope Limitations", expanded=False):
    st.markdown(
        """
        - **Synthetic Illustrative Data:** All hydrodynamic curves, bunker fuel prices, grid emission factors, and cargo demands are formulated strictly for demonstration and research purposes.
        - **Classical Computational Execution:** The Quantum-Inspired Evolutionary Algorithm (QIEA) is executed entirely on classical CPU hardware (NumPy/Python). No quantum hardware, simulators, or claims of quantum supremacy are involved.
        - **Feasibility Verification:** All comparisons benchmark the optimized plan against both a Feasible Naive Baseline (conventional HFO, fixed speed, no cold ironing) and the Best Conventional Baseline (HFO-only optimizer).
        """
    )
