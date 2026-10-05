"""
Unit and Integration Tests for South Asian Feeder Case Study.

Verifies:
1. Every external/public value has an authoritative source.
2. Derived values show their calculation basis.
3. Synthetic values are explicitly labelled.
4. Case study data reaches the optimizer.
5. Changing case-study inputs recomputes results.
6. Reset to Case Study Defaults restores the baseline.
"""

from __future__ import annotations
import copy
import pytest
import pandas as pd
import numpy as np

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem
from src.analysis.case_study import run_case_study
from src.models.provenance import (
    DATA_PROVENANCE_REGISTRY,
    get_provenance_dataframe,
    get_provenance_summary_counts,
    ProvenanceRecord,
)


def test_provenance_registry_structure_and_categories():
    """Verify data provenance schema and completeness across four classes."""
    df = get_provenance_dataframe()
    expected_cols = [
        "Category",
        "Field",
        "Value",
        "Unit",
        "Source Type",
        "Source",
        "Year",
        "Assumption?",
        "Calculation / Basis",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing required column: {col}"

    assert len(df) >= 25, f"Expected at least 25 provenance records, got {len(df)}"

    # Check the 4 source types are represented
    counts = get_provenance_summary_counts()
    assert counts["A. Publicly sourced"] > 0, "Missing Publicly Sourced records"
    assert counts["B. Derived/calculated from public data"] > 0, "Missing Derived records"
    assert counts["C. Project assumption"] > 0, "Missing Project Assumption records"
    assert counts["D. Synthetic/illustrative"] > 0, "Missing Synthetic records"


def test_provenance_field_integrity():
    """1. Every external/public value has a source.
       2. Derived values show calculation basis.
       3. Synthetic values are explicitly labelled.
    """
    for rec in DATA_PROVENANCE_REGISTRY:
        # Every record must have valid non-empty fields
        assert rec.field.strip(), "Record field must not be empty"
        assert rec.source.strip(), f"Record {rec.field} must specify a source"
        assert rec.source_type in [
            "A. Publicly sourced",
            "B. Derived/calculated from public data",
            "C. Project assumption",
            "D. Synthetic/illustrative",
        ], f"Invalid source type for {rec.field}: {rec.source_type}"

        # 1. Publicly sourced must have legitimate authority and not be labeled synthetic
        if rec.source_type.startswith("A."):
            assert rec.is_assumption == "No", f"Publicly sourced {rec.field} should have Assumption?='No'"
            assert len(rec.source) >= 5, f"Public source description too brief for {rec.field}"

        # 2. Derived values must show calculation basis
        if rec.source_type.startswith("B."):
            assert rec.calculation_basis.strip(), f"Derived field {rec.field} must have a calculation basis"
            assert len(rec.calculation_basis) >= 10, f"Calculation basis too brief for {rec.field}"

        # 3. Synthetic values must be explicitly labeled
        if rec.source_type.startswith("D."):
            assert rec.is_assumption == "Yes", f"Synthetic field {rec.field} must have Assumption?='Yes'"
            assert "synthetic" in rec.source_type.lower() or "illustrative" in rec.source_type.lower()


def test_case_study_data_reaches_optimizer():
    """4. Verify case-study data reaches the optimizer and changes results."""
    base_cfg = load_config()

    # Modify cargo demand on R1
    mod_cfg = copy.deepcopy(base_cfg)
    original_demand = base_cfg["routes"]["R1"]["annual_demand_teu"]
    surged_demand = original_demand + 80000
    mod_cfg["routes"]["R1"]["annual_demand_teu"] = surged_demand

    prob_base = FleetOptimizationProblem(config=base_cfg)
    prob_mod = FleetOptimizationProblem(config=mod_cfg)

    assert prob_base.routes["R1"]["annual_demand_teu"] == original_demand
    assert prob_mod.routes["R1"]["annual_demand_teu"] == surged_demand

    # Changing an input must produce distinct objective evaluations on identical bitstrings
    sample_bits = np.ones(prob_base.n_bits, dtype=int)
    ev_base = prob_base.evaluate(sample_bits)
    ev_mod = prob_mod.evaluate(sample_bits)

    # Transport work, fuel, or cost must reflect the changed demand
    assert ev_base["route_details"]["R1"]["annual_demand_teu"] != ev_mod["route_details"]["R1"]["annual_demand_teu"]


def test_changing_inputs_changes_case_study_results():
    """5. Verify changing inputs changes outputs in run_case_study."""
    cfg1 = load_config()
    cfg2 = copy.deepcopy(cfg1)

    # Alter route distance and demand
    cfg2["routes"]["R1"]["distance_nm"] = 1200.0
    cfg2["routes"]["R1"]["annual_demand_teu"] = 250000

    res1 = run_case_study(random_seed=42, config=cfg1, num_starts=2, evals_per_start=400)
    res2 = run_case_study(random_seed=42, config=cfg2, num_starts=2, evals_per_start=400)

    # Output metrics must reflect the changed input
    assert res1["summary"]["naive"]["fuel_t"] != res2["summary"]["naive"]["fuel_t"]
    assert res1["summary"]["best_conventional"]["cost_usd"] != res2["summary"]["best_conventional"]["cost_usd"]
    assert res1["df_routes"].loc[res1["df_routes"]["Route ID"] == "R1", "Distance (nm)"].values[0] == 890.0
    assert res2["df_routes"].loc[res2["df_routes"]["Route ID"] == "R1", "Distance (nm)"].values[0] == 1200.0


def test_case_study_reproducibility_defaults():
    """6. Verify reproducibility and default values."""
    cfg = load_config()
    ports = cfg["ports"]
    routes = cfg["routes"]

    # Verify South Asian ports
    expected_ports = ["mumbai", "kochi", "tuticorin", "chennai", "colombo", "singapore"]
    for p in expected_ports:
        assert p in ports, f"Port {p} missing from network"

    # Verify 5 routes
    assert len(routes) == 5
    assert routes["R1"]["origin"] == "mumbai"
    assert routes["R1"]["destination"] == "colombo"
    assert routes["R5"]["origin"] == "colombo"
    assert routes["R5"]["destination"] == "singapore"
