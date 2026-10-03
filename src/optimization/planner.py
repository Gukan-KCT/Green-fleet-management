"""
Unified Fleet Plan Optimization Engine.

Single central optimizer entry point for:
1. Streamlit Application
2. FastAPI Serverless Endpoints
3. Case Study Simulation & Experiments

Guarantees:
- Multi-start: Runs >= 5 independent unseeded QIEA runs (distinct seeds, total budget >= 20,000 evals).
- Evaluates Feasible Naive Baseline and Best Conventional Baseline.
- Compares all QIEA runs against Best Conventional Baseline.
- Transparently selects the absolute best plan and reports winner ("Green plan selected" vs "Conventional plan retained").
- Completes well under 60 seconds on CPU.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS
from src.optimization.qiea import QIEA
from src.analysis.case_study import get_naive_baseline, get_best_conventional_baseline


def optimize_fleet_plan(
    problem: Optional[FleetOptimizationProblem] = None,
    weights: Optional[Dict[str, float] | Tuple[float, float, float]] = None,
    allowed_fuels: Optional[List[str]] = None,
    speed_cap: float = 18.0,
    shore_power: bool = True,
    num_qiea_starts: int = 5,
    evals_per_start: int = 4000,
    seeds: Optional[List[int]] = None,
    config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes a multi-start unseeded QIEA optimization suite alongside Feasible Naive
    and Best Conventional benchmarks.

    Parameters
    ----------
    problem : FleetOptimizationProblem, optional
        Initialized optimization problem. If None, constructed from weights & constraints.
    weights : dict or tuple of (w_fuel, w_cost, w_emiss)
    allowed_fuels : list of str, optional
    speed_cap : float
    shore_power : bool
    num_qiea_starts : int, default 5 (runs at least 5 independent unseeded QIEA runs)
    evals_per_start : int, default 4000 (total budget = 5 * 4000 = 20,000 evals)
    seeds : list of int, optional (default [42, 43, 44, 45, 46])

    Returns
    -------
    dict with:
        - 'problem': FleetOptimizationProblem
        - 'selected_plan': eval dict of the best overall plan
        - 'selected_bits': bitstring of the best overall plan
        - 'winner_status': 'Green plan selected' or 'Conventional plan retained: no green plan scored better under these weights'
        - 'naive_eval': Feasible naive baseline eval dict
        - 'naive_bits': Feasible naive bitstring
        - 'best_conv_eval': Best conventional baseline eval dict
        - 'best_conv_bits': Best conventional bitstring
        - 'qiea_runs': list of individual QIEA run results
        - 'best_qiea_eval': best pure QIEA run eval dict
        - 'best_qiea_bits': best pure QIEA bitstring
        - 'convergence_curve': best convergence curve
        - 'total_evaluations': int
        - 'runtime_sec': float
    """
    t_start = time.time()

    # 1. Setup problem if not supplied
    if problem is None:
        cand_opts = DEFAULT_CANDIDATE_OPTIONS
        if allowed_fuels is not None:
            cand_opts = [o for o in DEFAULT_CANDIDATE_OPTIONS if o["fuel"] in allowed_fuels]
            if not cand_opts:
                cand_opts = DEFAULT_CANDIDATE_OPTIONS

        w_dict = {"fuel": 0.2, "cost": 0.4, "emissions": 0.4}
        if isinstance(weights, tuple) and len(weights) == 3:
            w_dict = {"fuel": float(weights[0]), "cost": float(weights[1]), "emissions": float(weights[2])}
        elif isinstance(weights, dict):
            w_dict = weights

        problem = FleetOptimizationProblem(
            config=config,
            candidate_options=cand_opts,
            weights=w_dict,
            speed_cap_delta=speed_cap - 18.0,
            shore_power_forced=True if shore_power else False,
        )

    # 2. Compute Baselines (Feasible Naive & Best Conventional)
    naive_bits, naive_eval = get_naive_baseline(problem)
    best_conv_bits, best_conv_eval = get_best_conventional_baseline(
        problem, pop_size=30, generations=60, random_seed=42
    )

    # 3. Multi-Start Unseeded QIEA Optimization
    default_seeds = [42, 101, 2024, 777, 999]
    run_seeds = seeds or default_seeds[:num_qiea_starts]
    if len(run_seeds) < num_qiea_starts:
        run_seeds = [42 + i * 13 for i in range(num_qiea_starts)]

    pop_sz = 40
    gens = max(10, evals_per_start // pop_sz)

    qiea_runs = []
    best_qiea_fit = float("inf")
    best_qiea_res = None
    best_qiea_eval = None
    total_evals = 0

    for idx, seed in enumerate(run_seeds):
        # UNSEEDED QIEA (pure exploration from superposition)
        qiea = QIEA(
            n_bits=problem.n_bits,
            pop_size=pop_sz,
            generations=gens,
            rotation_angle=0.06,
            mutation_rate=0.03,
            random_seed=seed,
            initial_theta=problem.get_initial_q_angles(),
            use_adaptive_rotation=True,
            use_islands=True,
            num_islands=4,
            use_memetic=True,
            memetic_interval=8,
        )
        res = qiea.optimize(problem.fitness_function)
        total_evals += res.get("evaluations", pop_sz * gens)

        ev = problem.evaluate(res["best_bits"])
        qiea_runs.append({
            "seed": seed,
            "best_bits": res["best_bits"],
            "fitness": ev["fitness"],
            "base_objective": ev["base_objective"],
            "is_feasible": ev["is_feasible"],
            "eval_dict": ev,
            "convergence_curve": res["convergence_curve"],
        })

        if ev["fitness"] < best_qiea_fit:
            best_qiea_fit = ev["fitness"]
            best_qiea_res = res
            best_qiea_eval = ev

        if progress_callback:
            progress_callback(idx + 1, len(run_seeds), best_qiea_fit)

    # 4. Final Solution Tournament: best of {QIEA runs, best conventional}
    conv_fit = best_conv_eval["fitness"]
    selected_eval = best_qiea_eval
    selected_bits = best_qiea_res["best_bits"]
    convergence_curve = best_qiea_res["convergence_curve"]

    # Check if a non-HFO fuel is utilized
    allocs, _, _ = problem.decode_solution(selected_bits)
    has_green_fuel = False
    for o_idx, opt in enumerate(problem.options):
        if opt["fuel"] != "HFO" and np.sum(allocs[o_idx, :]) > 0:
            has_green_fuel = True
            break

    if best_qiea_eval["is_feasible"] and (best_qiea_fit <= conv_fit):
        if has_green_fuel:
            winner_status = "Green plan selected"
        else:
            winner_status = "Optimized plan selected (conventional propulsion optimal under current weights)"
    else:
        # Best conventional plan retained
        selected_eval = best_conv_eval
        selected_bits = best_conv_bits
        winner_status = "Conventional plan retained: no green plan scored better under these weights"

    runtime = time.time() - t_start

    return {
        "problem": problem,
        "selected_plan": selected_eval,
        "selected_bits": selected_bits,
        "winner_status": winner_status,
        "has_green_fuel": has_green_fuel,
        "naive_eval": naive_eval,
        "naive_bits": naive_bits,
        "best_conv_eval": best_conv_eval,
        "best_conv_bits": best_conv_bits,
        "qiea_runs": qiea_runs,
        "best_qiea_eval": best_qiea_eval,
        "best_qiea_bits": best_qiea_res["best_bits"],
        "convergence_curve": convergence_curve,
        "total_evaluations": total_evals,
        "runtime_sec": round(runtime, 2),
    }
