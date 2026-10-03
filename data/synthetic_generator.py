"""
Synthetic Fuel Consumption Data Generator.

Generates realistic synthetic operational voyage records combining:
1. Ground-truth hydrodynamics from the physics model (cubic speed law, Admiralty displacement law)
2. Hydrodynamic wave interaction non-linearities (shallow water & hull boundary layer interaction)
3. Operational random noise (stochastic sea state, sensor noise, wind fluctuations)

All generated data is strictly SYNTHETIC for demonstration and modeling.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

# Add project root to sys.path to enable direct execution
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.physics import calculate_leg_fuel_conventional, load_config


def generate_synthetic_dataset(
    n_samples: int = 6500,
    random_seed: int = 42,
    output_path: str | Path = "data/synthetic_fuel.csv",
) -> pd.DataFrame:
    """
    Generate synthetic fuel consumption records and write to CSV with synthetic disclaimer headers.
    """
    rng = np.random.default_rng(random_seed)
    config = load_config()
    vessel_types = list(config["vessel_types"].keys())

    records = []
    k_w = float(config["general"].get("weather_penalty_k_w", 0.35))

    for _ in range(n_samples):
        vessel_key = rng.choice(vessel_types)
        vessel_cfg = config["vessel_types"][vessel_key]

        v_min = float(vessel_cfg["v_min_knots"])
        v_max = float(vessel_cfg["v_max_knots"])
        v_ref = float(vessel_cfg["v_ref_knots"])
        dwt = float(vessel_cfg["capacity_dwt"])

        # Operational distributions
        speed = float(rng.uniform(v_min, v_max))
        # Cargo load between 15% and 98% of deadweight tonnage
        load = float(rng.uniform(0.15 * dwt, 0.98 * dwt))
        # Voyage distances typical for short-sea and regional coastal feeders
        distance = float(rng.uniform(120.0, 1850.0))
        # Weather severity: Beta distributed with mean ~0.3
        weather = float(rng.beta(2.0, 4.5))

        # Auxiliary synthetic features
        sea_state = int(np.clip(np.round(weather * 8.0 + rng.normal(0, 0.5)), 0, 8))
        hull_roughness = float(rng.uniform(0.96, 1.14))  # Biofouling degradation multiplier

        # Base physics calculation
        base_fuel, _ = calculate_leg_fuel_conventional(
            vessel_cfg=vessel_cfg,
            speed_knots=speed,
            distance_nm=distance,
            cargo_load_tonnes=load,
            weather_severity=weather,
            k_w=k_w,
        )

        # Non-linear wave drag & hydrodynamic resistance at high speeds (Froude number surge)
        speed_ratio = speed / v_ref
        wave_surge = 0.05 * (speed_ratio**4.2) * (1.0 + 0.15 * (sea_state / 8.0))

        # Multiplicative stochastic noise: lognormal with 3.5% std
        noise = rng.lognormal(mean=0.0, sigma=0.035)

        # Hull condition multiplier
        fuel_consumed = (base_fuel * (1.0 + wave_surge) * hull_roughness) * noise

        records.append(
            {
                "vessel_type": vessel_key,
                "speed_knots": round(speed, 2),
                "cargo_load_tonnes": round(load, 1),
                "distance_nm": round(distance, 1),
                "weather_severity": round(weather, 3),
                "sea_state": sea_state,
                "hull_condition": round(hull_roughness, 3),
                "fuel_consumed_tonnes": round(fuel_consumed, 3),
            }
        )

    df = pd.DataFrame(records)

    # Ensure output directory exists
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Write file with explicit disclaimer comment banner in CSV header
    disclaimer = (
        "# NOTICE: THIS DATASET IS COMPLETELY SYNTHETIC AND GENERATED FOR RESEARCH/DEMO PURPOSES ONLY.\n"
        "# DO NOT USE THESE VALUES FOR ACTUAL NAVIGATION OR COMMERCIAL MARITIME DECISIONS.\n"
    )
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(disclaimer)
        df.to_csv(f, index=False)

    print(f"Generated {len(df)} synthetic records written to {out_file.resolve()}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic vessel fuel dataset.")
    parser.add_argument("--rows", type=int, default=6500, help="Number of records to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--out", type=str, default="data/synthetic_fuel.csv", help="Output CSV path")
    args = parser.parse_args()

    generate_synthetic_dataset(n_samples=args.rows, random_seed=args.seed, output_path=args.out)
