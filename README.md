# Quantum-Inspired Green Fleet Management Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit UI](https://img.shields.io/badge/Streamlit-Primary%20UI-red.svg)](https://streamlit.io/)
[![Classical CPU Only](https://img.shields.io/badge/Hardware-Classical%20CPU%20Only-emerald.svg)]()

A decision support platform for maritime fleet deployment optimization, voyage fuel consumption modeling, alternative marine fuel evaluation, port shore power analysis, and quantum-inspired algorithmic benchmarking.

---

> ### ⚠️ Mandatory Synthetic Data & Scientific Disclaimers
> 1. **Primary Interface:** Streamlit is the verified primary user interface (`app/Home.py`). The optional lightweight REST API (`api/index.py`) and static web frontend (`public/`) are provided strictly as an optional demo.
> 2. **Hosting Provider Limits:** Note that any deployment resource constraints, timeout boundaries, and memory limits must be checked in the hosting provider's current documentation. The platform is designed and verified for local execution.
> 3. **Synthetic Data Notice:** All operational voyage records, fuel consumption telemetry, emissions factors, and economic costs in this platform are **strictly synthetic and illustrative** for prototype demonstration. Never present these numbers as real-world navigational data.
> 4. **Quantum-Inspired Algorithm Notice:** "Quantum-inspired" denotes **classical algorithms running on standard classical CPUs** that borrow mathematical concepts from quantum computing (Q-bit probabilistic angular representation, superposition-like state exploration, and rotation-gate update operators). **No quantum hardware, Qiskit libraries, or quantum simulators are used, and no quantum advantage is claimed.**
> 5. **Illustrative Parameters:** All physical constants, fuel prices, and emission factors are centralized in `config/params.yaml` and marked as illustrative placeholders requiring verification against primary maritime sources prior to commercial deployment.

---

## 1. Quick Start

### Installation (Streamlit Primary UI)
```bash
# 1. Clone repository and navigate to root
cd green_fleet

# 2. Install dependencies (Python 3.10+)
pip install -r requirements.txt
```

### Launch Interactive Streamlit Multi-Page App
```bash
streamlit run app/Home.py
```
Open your browser at `http://localhost:8501`.

### Optional API Demo (Optional)
If running the optional demo API/web interface:
```bash
pip install -r requirements-api.txt
uvicorn api.index:app --port 8000
```

### Run Unit Tests
```bash
pytest -v
```
Comprehensive tests verify baseline hierarchies, quantum-inspired determinism, constraint penalties, hash freshness, API reliability ranges, and Streamlit page smoke tests.

### Re-run Full Experimental Suite Headless
```bash
python scripts/run_experiments.py
```
Executes all benchmarks across multiple independent seeds, regenerates all precomputed artifacts in `data/*.pkl` with deterministic codebase SHA-256 hashes, and automatically writes the dossier to `docs/EXPERIMENTAL_RESULTS.md`.

---

## 2. Platform Architecture & Modules

```
green_fleet/
├── config/
│   └── params.yaml                   # Central parameter registry (illustrative constants)
├── data/
│   ├── synthetic_generator.py        # Generates ~6,500 synthetic voyage records
│   ├── synthetic_fuel.csv            # Synthetic operational dataset with disclaimer banner
│   └── saved_*.pkl                   # Precomputed benchmark & case study plans (with code hashes)
├── src/
│   ├── utils/
│   │   └── hashing.py                # SHA-256 codebase & params hash freshness checker
│   ├── models/
│   │   └── physics.py                # Hydrodynamic fuel, emissions, cost, & reliability formulas
│   ├── prediction/
│   │   ├── baselines.py              # Polynomial Ridge & Gradient Boosting regressors
│   │   ├── q_predictor.py            # QIEA feature-selection and hyperparameter optimizer
│   │   ├── evaluator.py              # Cross-validation & Wilcoxon signed-rank paired tests
│   │   └── fuel_model.py             # Unified FuelModel API (physics vs ML toggle)
│   ├── optimization/
│   │   ├── qiea.py                   # Quantum-Inspired Evolutionary Algorithm engine
│   │   ├── baselines.py              # Memetic GA, PSO, Hill Climbing, Random Search
│   │   ├── problem.py                # Fleet problem encoding, objective & constraint evaluators
│   │   ├── planner.py                # Unified unseeded multi-start QIEA fleet planner
│   │   └── pareto.py                 # Multi-objective weighted-sum sweep & non-dominated filter
│   └── analysis/
│       ├── fuels.py                  # Techno-economic alternative marine fuels comparison
│       ├── shore_power.py            # Port berth cold ironing vs auxiliary generator analysis
│       ├── scenarios.py              # Sensitivity & stress-testing scenario manager
│       ├── benchmark.py              # Fair multi-seed algorithmic & scalability benchmark suite
│       ├── case_study.py             # Four-plan case study (Naive, Conv, Balanced, Green)
│       └── report.py                 # Downloadable standalone HTML & CSV report generator
├── app/
│   ├── Home.py                       # Main portal, staleness alerts & executive dashboard
│   ├── ui/
│   │   ├── state.py                  # Session state & cached plan loader with hash verification
│   │   └── theme.py                  # Unified color tokens, typography & chart palettes
│   └── pages/                        # 8 interactive Streamlit analysis pages
├── api/                              # Optional demo REST API
├── public/                           # Optional demo web frontend
├── docs/
│   ├── ALGORITHM.md                  # QIEA mathematical derivation & pseudocode
│   ├── IMPLEMENTATION_GUIDE.md       # Operator guide & customization procedures
│   └── EXPERIMENTAL_RESULTS.md       # Benchmark dossier generated by run_experiments.py
├── scripts/
│   └── run_experiments.py            # Headless script to execute all benchmarks & update docs
├── tests/                            # Test suite (physics, constraints, optimization, pass 3 reqs)
├── requirements.txt                  # Streamlit + Pytest + core scientific dependencies
├── requirements-api.txt              # FastAPI + Uvicorn (optional demo)
└── README.md
```

---

## 3. Mathematical Formulations & Assumptions

### (a) Propulsion Fuel Consumption per Sea Leg
$$\text{Fuel}_{\text{leg}} = F_{\text{ref}} \left(\frac{V}{V_{\text{ref}}}\right)^3 \times \left(\frac{\Delta_{\text{lightship}} + L}{\Delta_{\text{lightship}} + L_{\text{ref}}}\right)^{2/3} \times (1 + k_w \cdot S_w) \times \frac{d}{24 \cdot V}$$
- **Cubic Speed Law:** Propulsion power and daily fuel burn scale with velocity cubed ($V^3$).
- **Displacement Scaling:** Immersed hull resistance follows the classical Admiralty formula ($\nabla^{2/3}$).
- **Weather Penalty:** Linear multiplier $1 + k_w \cdot S_w$ with sensitivity $k_w = 0.35$.
- **Transit Duration:** Distance $d$ divided by speed $24 \cdot V$.

### (b) Alternative Fuel Energy Equivalence
$$M_{\text{alt}} = M_{\text{conv}} \times \left(\frac{LHV_{\text{conv}}}{LHV_{\text{alt}}}\right) \times \frac{1}{\eta_{\text{rel}}}$$
Converts conventional fuel burn (HFO baseline) to alternative fuel mass by matching net shaft mechanical work.

### (c) Well-to-Wake Lifecycle GHG Emissions
$$E_{\text{total}} = M_{\text{fuel}} \cdot \Big(EF_{\text{TtW}} + EF_{\text{WtT}}(\text{pathway})\Big) + M_{\text{fuel}} \cdot \xi_{\text{slip}}$$
- Separate Tank-to-Wake (combustion) and Well-to-Tank (upstream extraction/synthesis) emission factors.
- Production pathway selectors for Methanol, Ammonia, and Hydrogen (Grey, Blue with CCS, Green renewable e-fuel).
- Unburned slip terms for methane slip (LNG) and $N_2O$ slip (ammonia).

### (d) Operating Cost Formulation
$$\text{Cost} = C_{\text{fuel}} + C_{\text{charter}} + C_{\text{port\_fees}} + C_{\text{shore\_power}} + \tau_{\text{carbon}} \cdot E_{\text{total}}$$
Accounts for fuel market prices, vessel fixed charter/capital costs, port mooring tariffs, shore electricity charges, and an illustrative carbon price ($\tau_{\text{carbon}} = \$80 / \text{t CO}_2\text{e}$).

### (e) Usable Cargo Capacity Penalty
$$\text{Capacity}_{\text{usable}} = \text{Capacity}_{\text{nominal}} \times \left(1 - \frac{\delta_{\text{penalty}}}{100}\right)$$
Penalizes cargo slot capacity for lower volumetric energy density fuels (e.g. up to 14% loss for liquid hydrogen cryogenic tanks).

### (f) Operational Schedule Reliability Index
$$R(V, S_w) = \max\left(0, \min\left(1.0, 1.0 - 0.25 \left(\frac{V}{V_{\max}}\right)^2 - 0.20 \cdot S_w\right)\right)$$
Reflects delay recovery buffer: reliability drops quadratically near engine maximum rating ($V_{\max}$) and drops with adverse sea states ($S_w$).

---

## 4. Empirical Evaluation & Experimental Results

All empirical performance figures and benchmark comparisons are dynamically produced by headless execution (`scripts/run_experiments.py`) and recorded in [`docs/EXPERIMENTAL_RESULTS.md`](docs/EXPERIMENTAL_RESULTS.md).

| Benchmark Domain | Rigorous Methodology & Data-Grounded Findings |
| :--- | :--- |
| **Fuel Prediction ML** | Evaluated on 6,500 synthetic voyage records via repeated 10-fold cross-validation (20 paired folds) and two-sided Wilcoxon signed-rank testing. Polynomial Ridge regression performs strongly due to the near-polynomial nature of classical hydrodynamic physics (cubic speed law and deadweight displacement curves). QIEA optimizes feature selection and Gradient Boosting hyperparameters. |
| **Optimization Credibility** | Evaluated across 10 independent random seeds with equal evaluation budgets (20,000 function evaluations per algorithm on the 101-bit case). QIEA, Memetic GA (with equal local search), PSO, Hill Climbing, and Random Search are compared on best fitness, mean fitness, variance, feasibility rate, and execution runtime, with dynamic reporting of true winners without predetermined narratives. |
| **Four-Plan Case Study** | Rigorous **public-data-informed / reproducible prototype case study** focusing on a realistic South Asian feeder network (Nhava Sheva, Kochi, Tuticorin, Chennai, Colombo, Singapore). Full data provenance structure categorizes all inputs into (A) Publicly sourced, (B) Derived from public data, (C) Project assumptions, and (D) Synthetic/illustrative. Systematically compares four distinct plans: (1) Feasible Naive Baseline, (2) Best Conventional Baseline, (3) Balanced Optimized Plan, and (4) Green Optimized Plan with live recomputation and reproducible default reset. |
| **Port Cold Ironing** | Quantifies port-side MGO diesel fuel avoided, lifecycle emissions changes, and net energy cost deltas based on terminal grid emission factors and electricity tariffs. |
| **Network Scalability** | Evaluated across Small ($L = 39$ bits), Medium ($L = 101$ bits), and Large ($L = 462$ bits, 24 synthetic corridors) networks across 10 independent seeds with scaled evaluation budgets. Documents why the 24-corridor network requires proportional operator fleet availability (120 vessels) to avoid structural infeasibility. |
