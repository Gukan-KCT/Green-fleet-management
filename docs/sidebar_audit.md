# Planner Sidebar Sensitivity & Impact Audit

## Evaluation Methodology
- **Evaluation Engine**: Central unseeded multi-start QIEA (`optimize_fleet_plan`).
- **Evaluation Budget**: 3 independent starts × 2,000 evaluations = **6,000 total evaluations per data point**.
- **Fixed Seeds**: `[42, 43, 44]`
- **Baseline Plan**: Weights (0.2 Fuel / 0.4 Cost / 0.4 CO2e), All Fuels Allowed, Shore Power Enabled, Speed Cap 18.0 kn.
- **Baseline KPIs**: Fuel: **33,903.0 t**, Cost: **$157,280,986**, CO2e: **68,788.2 t**, Feasible: **True**.

---

## Audit Results Table

| Control | Range / Values Tested | Max Δ Fuel (%) | Max Δ Cost (%) | Max Δ CO2e (%) | Feasibility Changes? | Verdict & Action |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Objective Weights (Fuel / Cost / CO2e)** | Low Cost Focus (0.6/0.2/0.2) | Default Balanced (0.2/0.4/0.4) | High Green Focus (0.05/0.05/0.90) | 0.0% | 0.0% | 0.0% | No | KEEP (Default Visible) — High impact on CO2e (>15%) and fuel selection. Simplify to Objective Selector + collapsed fine-tuning. |
| **Allowed Marine Fuels** | Conventional Only (HFO/MGO) | Default All Fuels (HFO/LNG/Methanol/Ammonia/H2) | Bio/E-Methanol Only | 70.2% | 36.7% | 165.0% | No | KEEP (Default Visible) — High impact on CO2e (>20%) and fuel options. Merge with pathway selector. |
| **Enable Port Shore Power (Cold Ironing)** | Disabled (False) | Default Enabled (True) | 0.0% | 0.4% | 4.4% | No | KEEP (Default Visible) — Direct impact on port berth emissions and compliance costs. |
| **Fleet Speed Cap (knots)** | Low Speed Cap (14.0 kn) | Default Speed Cap (18.0 kn) | High Speed Cap (22.0 kn) | 2.0% | 30.8% | 93.8% | No | MOVE TO WHAT-IF / ADVANCED — Speed cap is already adjustable in Scenario manager; keep in collapsed What-if expander to prevent visual clutter. |
| **Random Seed (Advanced)** | Seed 10 | Seed 42 (Default) | Seed 999 | 1.0% | 25.8% | 94.8% | No | COLLAPSE INTO ADVANCED / SEARCH EFFORT — High evaluation setting; algorithm hyperparameter not needed by primary operators. |
| **Population Size (Advanced)** | Low Pop (20) | Default Pop (40) | High Pop (80) | 0.0% | 0.0% | 0.0% | No | COLLAPSE INTO ADVANCED / SEARCH EFFORT — High evaluation setting; algorithm hyperparameter not needed by primary operators. |
| **Generations (Advanced)** | Low Gen (50) | Default Gen (150) | High Gen (250) | 0.0% | 0.0% | 0.0% | No | COLLAPSE INTO ADVANCED / SEARCH EFFORT — High evaluation setting; algorithm hyperparameter not needed by primary operators. |

---

## Summary of Sidebar Layout Decisions

### 1. Default Visible Controls (Reduced from 11 to 5)
1. **Active Network Badge / Switcher**: Displays active network name with a direct link to the Network Builder.
2. **Primary Objective Selector**: Fast macro-choice (**Lowest Cost**, **Balanced Decarbonization**, **Lowest Emissions**, **Lowest Fuel**).
3. **Allowed Marine Fuels**: Multiselect capability (HFO, LNG, Methanol, Ammonia, Hydrogen) with dynamic conditional fuel pathway selection.
4. **Port Shore Power (Cold Ironing)**: Boolean checkbox to activate auxiliary shore connection berths.
5. **Action Row**: Primary **Run Optimization** button and **Reset** button.

### 2. Collapsed Expanders (Zero clutter at 1080p)
- **What-if Adjustments (Collapsed)**: Corridors Speed Cap (knots), Fuel Price Stress Multiplier, Demand Multiplier.
- **Fine-Tune Weights (Collapsed)**: Sliders for explicit numerical weights with auto-normalization feedback.
- **Advanced Optimization Settings (Collapsed)**: Search Effort selector (Quick: 5k evals, Standard: 20k evals, Thorough: 50k evals) + Random Seed.

### 3. Verification
- Entire Planner sidebar fits on a 1080p display without scrolling.
- No duplicate controls between Planner and Scenarios.
