"""
Home Landing Page - Quantum-Inspired Green Fleet Management Platform.
"""

import sys
from pathlib import Path
import streamlit as st

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import load_config

st.set_page_config(
    page_title="Green Fleet Platform | Home",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚢 Quantum-Inspired Green Fleet Management Platform")
st.markdown("### Decision Support System for Maritime Decarbonization & Fleet Optimization")

# ==============================================================================
# SYNTHETIC DATA & METHODOLOGY DISCLAIMER BANNER
# ==============================================================================
st.info(
    """
    **SYNTHETIC DATA & METHODOLOGY NOTICE:**  
    All operational voyage records, fuel consumption telemetry, emissions factors, and economic costs in this platform are **strictly synthetic and illustrative** for Phase-1 prototype demonstration. Verify all parameters against primary sources, classification societies, and official IMO regulatory frameworks before real-world operational use.
    
    **QUANTUM-INSPIRED ALGORITHM DISCLOSURE:**  
    "Quantum-inspired" refers to classical algorithms executed on standard classical CPUs that adopt mathematical principles from quantum information theory (e.g. Q-bit probabilistic representations, superposition-like state exploration, and rotation-gate update rules). **No quantum hardware, Qiskit libraries, or quantum simulators are used, and no quantum advantage is claimed.**
    """
)

# Load base configuration
cfg = load_config()

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Platform Capabilities")
    st.markdown(
        """
        The **Green Fleet Management Platform** integrates mathematical hydrodynamic models, quantum-inspired meta-heuristic optimization, and machine learning to address the maritime decarbonization trilemma:
        
        1. **Fuel Consumption Prediction:**  
           Accurately models vessel fuel burn under varying vessel types, payloads, speeds, distances, and sea states using both analytical physics and QIEA-tuned machine learning models.
        2. **Fleet Deployment Optimization:**  
           Solves the multi-objective combinatorial allocation problem: assigning vessel types and fuels across shipping routes, selecting cruising speeds, and scheduling shore power usage to minimize fuel, operating costs, and Well-to-Wake emissions subject to demand and reliability constraints.
        3. **Alternative Fuel Evaluation:**  
           Compares lifecycle emissions and costs across HFO, MGO, LNG, Methanol, Ammonia, and Liquid Hydrogen across grey, blue, and green production pathways.
        4. **Shore Power Cold-Ironing Analysis:**  
           Quantifies port-side air quality and carbon benefits of cold-ironing vs onboard auxiliary diesel generators.
        5. **Rigorous Algorithmic Benchmarking:**  
           Benchmarks the Quantum-Inspired Evolutionary Algorithm (QIEA) against Canonical Genetic Algorithms (GA), Particle Swarm Optimization (PSO), and Random Search on solution quality, convergence speed, and scalability.
        """
    )

with col2:
    st.subheader("System Profile")
    st.markdown(f"**Platform Version:** `{cfg['meta']['version']}`")
    st.markdown(f"**Execution Runtime:** Classical CPU (Python 3.11+)")
    st.markdown(f"**Routes in Base Network:** {len(cfg['routes'])} Feeder Corridors")
    st.markdown(f"**Vessel Types Modeled:** {len(cfg['vessel_types'])} Standard Feeder Classes")
    st.markdown(f"**Fuels Evaluated:** {len(cfg['fuels'])} Marine Fuels & Multiple Pathways")
    st.markdown(f"**Port Terminals Modeled:** {len(cfg['ports'])} Regional Ports")
    
    st.metric(
        label="Illustrative Carbon Price",
        value=f"${cfg['general']['carbon_price_usd_per_tonne']:.0f} / t CO2e",
        help="Global / regional carbon tax proxy from config/params.yaml",
    )
    st.metric(
        label="Commercial Operating Year",
        value=f"{cfg['general']['days_per_year']:.0f} Days / Year",
        help="Standard commercial operating days per vessel",
    )

st.markdown("---")
st.subheader("Navigation Guide")

nav_col1, nav_col2, nav_col3 = st.columns(3)

with nav_col1:
    st.markdown("#### 1. Models & Prediction")
    st.markdown("- **[1_Model](pages/1_Model.py):** Mathematical hydrodynamic formulas and configuration parameter tables.")
    st.markdown("- **[2_Fuel_Prediction](pages/2_Fuel_Prediction.py):** Regression baselines vs Quantum-Inspired predictor, paired Wilcoxon test, and interactive voyage fuel calculator.")
    st.markdown("- **[3_Fleet_Optimization](pages/3_Fleet_Optimization.py):** Multi-objective weights, Pareto front, convergence curves, and fleet deployment mix.")

with nav_col2:
    st.markdown("#### 2. Transition Analysis")
    st.markdown("- **[4_Alternative_Fuels](pages/4_Alternative_Fuels.py):** Techno-economic comparison of HFO, LNG, Methanol, Ammonia, and Hydrogen with production pathway selector.")
    st.markdown("- **[5_Shore_Power](pages/5_Shore_Power.py):** Cold-ironing port grid emissions and economic savings vs auxiliary diesel generators.")
    st.markdown("- **[6_Scenarios](pages/6_Scenarios.py):** Sensitivity stress-testing presets (fuel price surge, demand boom, strict carbon caps, rough weather).")

with nav_col3:
    st.markdown("#### 3. Verification & Case Study")
    st.markdown("- **[7_Benchmarking](pages/7_Benchmarking.py):** Multi-seed benchmark: QIEA vs GA vs PSO vs Random Search, convergence curves, and scalability plots.")
    st.markdown("- **[8_Case_Study](pages/8_Case_Study.py):** Conventional baseline vs optimized green feeder plan, 12-month simulation, and downloadable HTML/CSV report.")
