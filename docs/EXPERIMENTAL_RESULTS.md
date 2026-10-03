# Experimental Results & Benchmarking Dossier

> **DISCLAIMER:** All figures, operational costs, fuel consumptions, and lifecycle emissions in this dossier are derived from **strictly synthetic models** formulated for the Phase-1 prototype demonstration. No proprietary vessel telemetry or real commercial operations were utilized.

**Execution Status:** Full Reproducible Batch Run Completed  
**Code & Config Hash:** `e2394c9e4c280115`  
**Total Benchmark Runtime:** 4066.84 seconds  
**Hardware Profile:** Local Classical CPU (No Quantum Hardware, No Qiskit, No Emulators)  
**Cross-Validation:** Repeated 10-Fold CV (20 Paired Folds) with Two-Sided Wilcoxon Signed-Rank Test  
**Optimization Budget:** 20,000 Function Evaluations per Algorithm across 10 Independent Seeds  

---

## 1. Fuel Consumption Prediction Benchmark

Models were trained and evaluated on 6,500 synthetic voyage records (80/20 train/test split). A repeated 10-fold cross-validation (20 paired folds) with a two-sided **Wilcoxon signed-rank test** was conducted to verify statistical significance without bare fallbacks.

### 1.1 Model Performance Comparison (Test Set)

| Model Architecture | Test RMSE (tonnes) | Test MAE (tonnes) | Test $R^2$ Score | Optimization / Tuning |
| :--- | :---: | :---: | :---: | :--- |
| **Polynomial Ridge (Degree 2)** | 7.0418 | 5.0423 | 0.9906 | Analytical L2 Regularization |
| **Gradient Boosting (Default)** | 10.0418 | 6.9952 | 0.9809 | Fixed default hyperparameters |
| **Quantum-Inspired Predictor** | 6.5531 | 4.2915 | 0.9919 | QIEA Feature Selection & Hyperparameter Tuning |

### 1.2 Two-Sided Paired Wilcoxon Signed-Rank Significance Test

| Baseline Comparison | Wilcoxon W-Statistic | p-value | Statistically Significant ($p < 0.05$)? | Direction & Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **vs Polynomial Ridge** | 92.0 | 0.6477 | False | No statistically significant difference (p = 0.6477 >= 0.05, two-sided): QIEA-tuned model RMSE (6.9997) is comparable to Polynomial Ridge (7.0342 tonnes). |
| **vs Gradient Boosting** | 0.0 | 0.0000 | True | Statistically significant difference (p = 0.0000 < 0.05, two-sided): QIEA-tuned model achieved lower mean RMSE (6.9997 vs 10.4657 tonnes). |

> **Architectural Note on Hydrodynamic Data:** Polynomial Ridge regression closely matches or outperforms tree-based models on this benchmark because the synthetic data generation engine is grounded in classical naval architecture physics (cubic speed law $P \propto V^3$ and Admiralty coefficients with deadweight displacement scaling), which are near-polynomial by formulation.

---

## 2. Algorithmic Optimization Benchmark (Medium Network, L = 101 Bits)

Benchmarking of 5 optimization algorithms on the 5-route feeder network problem ($L = 101$ decision bits) over 10 independent seeds with identical evaluation budgets (20,000 evaluations per run).

### 2.1 Solution Quality and Convergence Summary

| Algorithm               |   Best Fitness |   Mean Fitness |   Std Fitness |   Feasibility Rate (%) |   Avg Runtime (s) |   Avg Evaluations |
|:------------------------|---------------:|---------------:|--------------:|-----------------------:|------------------:|------------------:|
| Genetic Algorithm (GA)  |         3.2702 |         3.5278 |        0.1908 |                    100 |             9.715 |             20000 |
| QIEA (Quantum-Inspired) |         3.7067 |         4.3046 |        0.4344 |                    100 |            14.653 |             20000 |
| Particle Swarm (PSO)    |         7.3804 |     15475.7    |    10831.8    |                     20 |            11.366 |             20000 |
| Hill-Climb Search       |         3.5463 |         3.7659 |        0.1275 |                    100 |             8.847 |             20000 |
| Random Search           |    215684      |    265558      |    26149.5    |                      0 |            16.145 |             20000 |

### 2.2 Data-Driven Algorithmic Narrative

**Empirical Benchmark Summary (5 Algorithms, Identical Evaluation Budget):**

- **Overall Winner**: **Genetic Algorithm (GA)** achieved the lowest mean composite fitness (**3.5278**) with a feasibility rate of **100.0%**.

- **Runner-Up**: **Hill-Climb Search** followed with mean fitness **3.7659** and **100.0%** feasibility.

- **Genetic Algorithm (GA)**: Mean fitness = 3.5278, Feasibility = 100.0%. Canonical two-point crossover and bit-flip mutation effectively assemble building blocks across route assignments.

- **Hill-Climb Search**: Mean fitness = 3.7659, Feasibility = 100.0%, Runtime = 8.85s (20,000 evals). Multi-start 1-bit-flip neighborhood search greedily climbs local gradients with random perturbation restarts.

- **QIEA (Quantum-Inspired)**: Mean fitness = 4.3046, Feasibility = 100.0%, Runtime = 14.65s (20,000 evals). Probabilistic Q-bit representation and dynamic rotation angle updates provide rapid exploration with low memory footprint.

- **Particle Swarm (PSO)**: Mean fitness = 15475.6595, Feasibility = 20.0%. With dynamic inertia weight decay (0.9 -> 0.4) and velocity clipping, binary PSO explores discrete hyperplanes.

- **Random Search**: Mean fitness = 265558.2612, Feasibility = 0.0%. Demonstrates the steep combinatorial challenge of satisfying simultaneous demand, frequency, vessel inventory, and reliability constraints without guided search.

---

## 3. Scalability Analysis across Network Dimensions

Evaluated across Small ($L=39$ bits), Medium ($L=101$ bits), and Large ($L=462$ bits, 24 routes) regional networks across 10 independent random seeds with scaled evaluation budgets.

| Scale                        |   Decision Bits (L) |   Evaluations | Algorithm               |     Best Fitness |     Mean Fitness |   Feasibility Rate (%) |   Avg Runtime (s) |
|:-----------------------------|--------------------:|--------------:|:------------------------|-----------------:|-----------------:|-----------------------:|------------------:|
| Small (3 Routes, 4 Options)  |                  39 |          8000 | Genetic Algorithm (GA)  |      1.6372      |      1.7502      |                    100 |             1.724 |
| Small (3 Routes, 4 Options)  |                  39 |          8000 | QIEA (Quantum-Inspired) |      1.8197      |      2.0067      |                    100 |             1.321 |
| Small (3 Routes, 4 Options)  |                  39 |          8000 | Particle Swarm (PSO)    |      1.8524      |    295.902       |                     80 |             0.818 |
| Small (3 Routes, 4 Options)  |                  39 |          8000 | Hill-Climb Search       |      1.6874      |      1.7906      |                    100 |             0.822 |
| Small (3 Routes, 4 Options)  |                  39 |          8000 | Random Search           |      1.9793      |  14048.2         |                     10 |             1.261 |
| Medium (5 Routes, 8 Options) |                 101 |         20000 | Genetic Algorithm (GA)  |      3.2702      |      3.5278      |                    100 |             4.287 |
| Medium (5 Routes, 8 Options) |                 101 |         20000 | QIEA (Quantum-Inspired) |      3.7067      |      4.3046      |                    100 |            11.809 |
| Medium (5 Routes, 8 Options) |                 101 |         20000 | Particle Swarm (PSO)    |      7.3804      |  15475.7         |                     20 |             9.253 |
| Medium (5 Routes, 8 Options) |                 101 |         20000 | Hill-Climb Search       |      3.5463      |      3.7659      |                    100 |             6.919 |
| Medium (5 Routes, 8 Options) |                 101 |         20000 | Random Search           | 215684           | 265558           |                      0 |            15.933 |
| Large (24 Routes, 8 Options) |                 462 |         30000 | Genetic Algorithm (GA)  |     19.2194      |   8277.09        |                     50 |            47.749 |
| Large (24 Routes, 8 Options) |                 462 |         30000 | QIEA (Quantum-Inspired) |  20491.1         |  39243.8         |                      0 |            43.195 |
| Large (24 Routes, 8 Options) |                 462 |         30000 | Particle Swarm (PSO)    | 546151           | 866507           |                      0 |            60.645 |
| Large (24 Routes, 8 Options) |                 462 |         30000 | Hill-Climb Search       |   6688.45        |  25936.5         |                      0 |            23.661 |
| Large (24 Routes, 8 Options) |                 462 |         30000 | Random Search           |      1.97363e+06 |      2.03678e+06 |                      0 |            88.789 |

---

## 4. Regional Feeder Case Study Results (Four Plan Comparison)

The South Asian feeder network is evaluated across **four distinct fleet deployment strategies**:
1. **Feasible Naive Baseline:** Conventional HFO, fixed service speed, no shore power.
2. **Best Conventional Baseline:** Optimizer restricted exclusively to conventional HFO options and no shore power.
3. **Balanced Multi-Objective Optimized Plan:** Multi-objective QIEA with equal weight on cost and emissions (0.2 fuel / 0.4 cost / 0.4 emissions).
4. **Green Multi-Objective Optimized Plan:** Multi-objective QIEA with emission-focused weights (0.1 fuel / 0.1 cost / 0.8 emissions).

### 4.1 Four-Plan Comparative Performance Matrix

| Metric | Feasible Naive | Best Conventional | Balanced Optimized | Green Optimized |
| :--- | :---: | :---: | :---: | :---: |
| **Total Fuel (t HFO-eq)** | 37,902.8 | 33,897.4 | 33,903.0 | 36,906.9 |
| **Operating Cost (USD)** | $112,145,985.0 | $116,764,244.0 | $157,280,986.0 | $157,607,062.0 |
| **Lifecycle GHG (t CO2e)** | 148,045.9 | 134,029.2 | 68,788.2 | 95,104.1 |
| **Carbon Intensity (g/t-nm)** | 12.51 | 11.32 | 5.81 | 8.03 |
| **Cost Delta vs Best Conv** | -4,618,259.0 USD (-4.0% decrease) | Reference ($0) | +40,516,742.6 USD (+34.7% increase) | +40,842,818.0 USD (+35.0% increase) |
| **CO2e Delta vs Best Conv** | +14,016.7 t CO2e (+10.5% increase) | Reference (0 t) | -65,241.0 t CO2e (-48.7% decrease) | -38,925.1 t CO2e (-29.0% decrease) |
| **CO2e Avoided vs Best Conv** | 0.0 t | Reference (0 t) | 65,241.0 t | 38,925.1 t |
| **Abatement Cost ($/tCO2e avoided)** | N/A | Reference | $621.0/t | $1049.3/t |
| **Constraint Feasibility** | Feasible (100%) | Feasible (100%) | Feasible (100%) | Feasible (100%) |

*Illustrative Carbon Price Reference:* **$80 / tCO2e**

### 4.2 Shore Power (Cold Ironing) Network Benefits
- **Port Fuel Avoided:** 2,919.5 tonnes MGO (91.2%)
- **Port CO2e Avoided:** 3,010.3 tonnes CO2e (24.4%)
- **Net Port Cost Delta:** $398,417.0

---
*Report generated autonomously by `scripts/run_experiments.py` from verified empirical data.*
