# Quantum-Inspired Green Fleet Management Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit UI](https://img.shields.io/badge/Streamlit-Multi--page-red.svg)](https://streamlit.io/)
[![Classical CPU Only](https://img.shields.io/badge/Hardware-Classical%20CPU%20Only-emerald.svg)]()

A locally runnable decision support platform for maritime fleet deployment optimization, voyage fuel consumption modeling, alternative marine fuel evaluation, port shore power analysis, and quantum-inspired algorithmic benchmarking.

---

> ### ⚠️ Mandatory Synthetic Data & Scientific Disclaimers
> 1. **Synthetic Data Notice:** All operational voyage records, fuel consumption telemetry, emissions factors, and economic costs in this platform are **strictly synthetic and illustrative** for Phase-1 prototype demonstration. Never present these synthetic numbers as real-world measurements or commercial navigational data.
> 2. **Quantum-Inspired Algorithm Notice:** "Quantum-inspired" denotes **classical algorithms running on standard classical CPUs** that borrow mathematical concepts from quantum computing (Q-bit probabilistic angular representation, superposition-like state exploration, and rotation-gate update operators). **No quantum hardware, Qiskit libraries, or quantum simulators are used, and no quantum advantage is claimed.**
> 3. **Illustrative Parameters:** All physical constants, fuel prices, and emission factors are centralized in `config/params.yaml` and marked as illustrative placeholders requiring verification against primary maritime sources (IMO, classification societies, engine OEMs) prior to commercial deployment.

---

## 1. Quick Start

### Installation
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

### Run Unit Tests
```bash
pytest -v
```
All 14 tests verify hydrodynamic monotonicity, energy equivalence, emissions arithmetic, constraint violations, QIEA determinism, and Pareto filtering.

### Re-run Full Experimental Suite Headless
```bash
python scripts/run_experiments.py
```
Executes all benchmarks across multiple independent seeds and automatically updates `docs/EXPERIMENTAL_RESULTS.md`.

---

## 2. Platform Architecture & Modules

```
green_fleet/
├── config/
│   └── params.yaml                   # Central parameter registry (illustrative constants)
├── data/
│   ├── synthetic_generator.py        # Generates ~6,500 synthetic voyage records
│   └── synthetic_fuel.csv            # Synthetic operational dataset with disclaimer banner
├── src/
│   ├── models/
│   │   └── physics.py                # Hydrodynamic fuel, emissions, cost, & reliability formulas
│   ├── prediction/
│   │   ├── baselines.py              # Polynomial Ridge & Gradient Boosting regressors
│   │   ├── q_predictor.py            # QIEA feature-selection and hyperparameter optimizer
│   │   ├── evaluator.py              # Cross-validation & Wilcoxon signed-rank paired tests
│   │   └── fuel_model.py             # Unified FuelModel API (physics vs ML toggle)
│   ├── optimization/
│   │   ├── qiea.py                   # Quantum-Inspired Evolutionary Algorithm engine
│   │   ├── baselines.py              # Binary GA, Continuous-to-Binary PSO, Random Search
│   │   ├── problem.py                # Fleet problem encoding, objective & constraint evaluators
│   │   └── pareto.py                 # Multi-objective weighted-sum sweep & non-dominated filter
│   └── analysis/
│       ├── fuels.py                  # Techno-economic alternative marine fuels comparison
│       ├── shore_power.py            # Port berth cold ironing vs auxiliary generator analysis
│       ├── scenarios.py              # Sensitivity & stress-testing scenario manager
│       ├── benchmark.py              # Multi-seed algorithmic & scalability benchmark suite
│       ├── case_study.py             # Regional feeder baseline vs optimized simulation
│       └── report.py                 # Downloadable standalone HTML & CSV report generator
├── app/
│   ├── Home.py                       # Main portal & synthetic data disclaimers
│   └── pages/
│       ├── 1_Model.py                # Mathematical formulation (st.latex) & parameter tables
│       ├── 2_Fuel_Prediction.py      # ML comparison, CV stats, predicted-vs-actual, interactive predict
│       ├── 3_Fleet_Optimization.py   # Weight sliders, Pareto front, convergence, allocation table
│       ├── 4_Alternative_Fuels.py    # Fuel comparison charts (mass, cost, lifecycle emissions, capacity)
│       ├── 5_Shore_Power.py          # Port-by-port cold-ironing grid vs engine analysis
│       ├── 6_Scenarios.py            # Presets & custom sensitivity stress tests
│       ├── 7_Benchmarking.py         # QIEA vs GA vs PSO vs Random Search (convergence, scalability)
│       └── 8_Case_Study.py           # Baseline vs Optimized feeder network, simulation, report download
├── docs/
│   ├── ALGORITHM.md                  # QIEA mathematical derivation & pseudocode
│   ├── IMPLEMENTATION_GUIDE.md       # Operator guide & customization procedures
│   └── EXPERIMENTAL_RESULTS.md       # Benchmark dossier generated by run_experiments.py
├── scripts/
│   └── run_experiments.py            # Headless script to execute all benchmarks & update docs
├── tests/
│   ├── test_physics.py               # Monotonicity, energy equivalence, emissions, capacity
│   ├── test_constraints.py           # Constraint checks & infeasibility flagging
│   └── test_optimization.py          # QIEA determinism, optimizer vs random baseline, Pareto
├── requirements.txt
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
| **Optimization Credibility** | Evaluated across 10 independent random seeds with equal evaluation budgets (20,000 function evaluations per algorithm on the 101-bit case). Algorithms are compared on best fitness, mean fitness, variance, feasibility rate, and execution runtime, with dynamic reporting of true winners without predetermined narratives. |
| **Dual-Baseline Case Study** | The optimized green fleet plan is systematically compared against two distinct feasible references: (a) Feasible Naive Baseline (conventional HFO, fixed speed, no shore power, adjusted until all constraints are satisfied) and (b) Best Conventional Baseline (optimizer restricted to HFO and no shore power). All performance deltas report signed changes (+ or -) with explicit words "increase" or "decrease". Transport work strictly uses cargo actually moved ($\min(\text{capacity}, \text{demand}) \times \text{distance}$) and tracks per-route oversupply ratios. |
| **Port Cold Ironing** | Quantifies port-side MGO diesel fuel avoided, lifecycle emissions changes, and net energy cost deltas based on terminal grid emission factors and electricity tariffs. |
| **Network Scalability** | Evaluated across Small ($L = 39$ bits), Medium ($L = 101$ bits), and Large ($L = 462$ bits, 24 synthetic corridors) networks across 10 independent seeds with scaled evaluation budgets. Documents why the 24-corridor network requires proportional operator fleet availability (120 vessels) to avoid structural infeasibility. |

---

## 5. Phase-2 Development Ideas (Out of Scope for Phase-1)

1. **Live AIS & Weather Integration:** Connect real-time Automatic Identification System (AIS) vessel tracking feeds and NOAA/Copernicus oceanic wave/wind reanalysis.
2. **Multi-Port Rotation Scheduling:** Extend single-corridor models to cyclic multi-port feeder loops with berth booking conflict resolution.
3. **Exact MILP Hybrid Solvers:** Couple QIEA meta-heuristics with exact Mixed-Integer Linear Programming (MILP) branch-and-bound solvers (e.g. HiGHS or SCIP) for provable optimality bounds.
4. **Official IMO CII Trajectory Modeling:** Implement the full IMO Carbon Intensity Indicator (CII) correction factors (A-E rating curves) through 2030 and 2050 targets.
5. **Fleet Retrofit & Capex Budgeting:** Model multi-year vessel engine dual-fuel retrofit capital expenditures (capex) and shipyard drydock scheduling.
