# Green Fleet Platform - Implementation & Operator Guide

This guide details the architecture, directory structure, customization procedures, and execution steps for the Phase-1 prototype of the Quantum-Inspired Green Fleet Management Platform.

---

## 1. Quick Start & Prerequisites

### Prerequisites
- Python 3.10+ (Tested on Python 3.11.7)
- Classical CPU (No specialized accelerators, quantum hardware, or external databases required)

### Setup in 3 Commands
```bash
# 1. Clone/navigate to directory
cd green_fleet

# 2. Install requirements
pip install -r requirements.txt

# 3. Launch interactive Streamlit multi-page dashboard
streamlit run app/Home.py
```

---

## 2. Directory & Module Architecture

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
│   ├── IMPLEMENTATION_GUIDE.md       # Operator guide & customization procedures (this file)
│   └── EXPERIMENTAL_RESULTS.md       # Automatically generated benchmark dossier
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

## 3. How to Extend the Configuration (`config/params.yaml`)

All physical constants, techno-economic parameters, and operational data are defined in `config/params.yaml`. **No parameters are hard-coded in logic.**

### 3.1 Adding a New Vessel Type
Append an entry under `vessel_types` in `config/params.yaml`:
```yaml
vessel_types:
  ultra_feeder:
    name: "Ultra Feeder (5,500 TEU)"
    capacity_teu: 5500
    capacity_dwt: 65000.0
    lightship_tonnes: 21000.0
    l_ref_tonnes: 52000.0
    v_min_knots: 13.0
    v_max_knots: 23.0
    v_ref_knots: 19.0
    f_ref_tonnes_day: 78.0
    daily_charter_usd: 46000.0
    aux_kw_berth: 1500.0
    fleet_available: 3
    description: "Post-Panamax regional corridor workhorse."
```

### 3.2 Adding a New Fuel Type
Append an entry under `fuels` in `config/params.yaml`:
```yaml
fuels:
  Bio_LNG:
    name: "Bio-LNG (Liquefied Biomethane)"
    is_conventional: false
    lhv_mj_kg: 49.0
    engine_efficiency_ratio: 1.03
    ef_tank_to_wake: 2.75
    ef_well_to_tank:
      green: -1.20 # Carbon-negative anaerobic digestion pathway
    price_usd_per_tonne:
      green: 1100.0
    capacity_penalty_pct: 3.5
    slip_factor_co2e_per_tonne: 0.12
    pathways: ["green"]
    default_pathway: "green"
```

### 3.3 Adding a New Shipping Route
Append an entry under `routes` in `config/params.yaml`:
```yaml
routes:
  R6:
    id: "R6"
    name: "Mumbai - Singapore Express"
    origin: "mumbai"
    destination: "singapore"
    distance_nm: 2420.0
    annual_demand_teu: 180000
    min_sailings_per_week: 1.0
    weather_severity: 0.35
    speed_cap_knots: 19.0
```

---

## 4. Running Experiments and Tests

### Run Unit Test Suite
```bash
pytest -v
```
Verifies:
1. Speed, load, and weather monotonicity of fuel hydrodynamics.
2. Fuel energy equivalence conversions.
3. Well-to-Wake emission factor summation.
4. Usable cargo capacity penalties.
5. Infeasibility flagging for demand, frequency, availability, bunkering, and carbon intensity violations.
6. Bit-for-bit QIEA determinism across identical random seeds.
7. Optimizer performance strictly superior to random search.

### Re-run Full Experimental Suite Headless
```bash
python scripts/run_experiments.py
```
Executes all benchmarks across multiple random seeds and writes updated figures and tables directly to `docs/EXPERIMENTAL_RESULTS.md`.
