"""
Quantum-Inspired Evolutionary Algorithm (QIEA) for Combinatorial Fleet Optimization.

Key Principles & Extensions:
1. Q-bit probabilistic representation:
   Each quantum-inspired bit (Q-bit) is represented by an angle theta in [0, pi/2].
   The probability of observing state 1 is sin^2(theta), and state 0 is cos^2(theta).
2. Superposition Initialization:
   Angles are initialized to theta = pi / 4 (or problem-specific initial angles such as
   sparse allocations with pi / 8).
3. Measurement / Collapse:
   Binary candidate solutions are sampled probabilistically from the Q-bit angular distributions.
4. Quantum Rotation Gate with Han & Kim lookup:
   Angles are incrementally rotated toward elite solutions (island-best or global-best)
   using direction-aware delta angles.
5. Adaptive Rotation Angle:
   Decays dynamically across evaluations (theta_max to theta_min) to balance initial exploration
   with refined terminal convergence.
6. Island Sub-Populations & Migration:
   Partitions the population into semi-isolated sub-populations with ring migration to prevent
   premature entropy loss and diversity collapse.
7. Optional Memetic Local Search:
   Applies periodic 1-bit-flip neighborhood search to the global best, counting all evaluations
   against the identical computational budget.
8. Optional Constraint Repair Operator:
   Repairs constraint shortfalls before fitness scoring.
"""

from __future__ import annotations
import math
from typing import Callable, Dict, Any, List, Optional
import numpy as np


class QIEA:
    """
    Quantum-Inspired Evolutionary Algorithm (modular & ablatable).
    Minimizes an objective function f(x) where x is a binary bitstring.
    """

    def __init__(
        self,
        n_bits: int,
        pop_size: int = 50,
        generations: int = 400,
        rotation_angle: float = 0.05,
        mutation_rate: float = 0.02,
        migration_interval: int = 10,
        random_seed: int = 42,
        initial_theta: Optional[float | np.ndarray] = None,
        use_adaptive_rotation: bool = True,
        use_islands: bool = True,
        num_islands: int = 5,
        use_memetic: bool = True,
        memetic_interval: int = 8,
        repair_func: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        record_q_history: bool = False,
    ):
        self.n_bits = n_bits
        self.pop_size = pop_size
        self.generations = generations
        self.record_q_history = record_q_history
        self.q_prob_history_: List[np.ndarray] = []
        self.total_budget = pop_size * generations
        self.rotation_angle = rotation_angle
        self.mutation_rate = mutation_rate
        self.migration_interval = migration_interval
        self.random_seed = random_seed
        self.initial_theta = initial_theta

        # Ablatable feature switches
        self.use_adaptive_rotation = use_adaptive_rotation
        self.use_islands = use_islands
        self.num_islands = num_islands if use_islands else 1
        self.use_memetic = use_memetic
        self.memetic_interval = memetic_interval
        self.repair_func = repair_func

        # Internal state
        self.evaluations_count_ = 0
        self.best_bits_: Optional[np.ndarray] = None
        self.best_fitness_: float = float("inf")
        self.convergence_curve_: List[float] = []

    def optimize(
        self,
        fitness_func: Callable[[np.ndarray], float],
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        seed_bits: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Execute QIEA optimization minimizing fitness_func.
        All function evaluations (including memetic and repair steps) are counted
        against the total evaluation budget.
        """
        rng = np.random.default_rng(self.random_seed)
        self.evaluations_count_ = 0
        self.convergence_curve_ = []

        num_islands = self.num_islands
        island_size = max(1, self.pop_size // num_islands)

        # 1. Initialize Q-bit population for each island
        if self.initial_theta is None:
            init_angles = np.full(self.n_bits, math.pi / 4.0)
        elif isinstance(self.initial_theta, (int, float)):
            init_angles = np.full(self.n_bits, float(self.initial_theta))
        else:
            init_angles = np.asarray(self.initial_theta, dtype=float)

        q_pops = [
            np.tile(init_angles, (island_size, 1)) for _ in range(num_islands)
        ]

        # Tracking population observations and bests
        p_best_bits = [np.zeros((island_size, self.n_bits), dtype=int) for _ in range(num_islands)]
        p_best_fitness = [np.full(island_size, float("inf")) for _ in range(num_islands)]

        island_best_bits = [None for _ in range(num_islands)]
        island_best_fitness = [float("inf") for _ in range(num_islands)]

        global_best_bits = None
        global_best_fitness = float("inf")

        if seed_bits is not None:
            seed_fit = float(fitness_func(seed_bits))
            self.evaluations_count_ += 1
            global_best_fitness = seed_fit
            global_best_bits = seed_bits.copy()

        gen = 0
        gen_eval_step = self.pop_size

        while self.evaluations_count_ < self.total_budget:
            gen += 1

            # Determine rotation angle for this generation
            if self.use_adaptive_rotation:
                theta_max = 0.08
                theta_min = 0.01
                progress = min(1.0, self.evaluations_count_ / max(1, self.total_budget))
                rot_angle = theta_max - (theta_max - theta_min) * progress
            else:
                rot_angle = self.rotation_angle

            # 2. Measurement and evaluation across sub-populations
            for isl in range(num_islands):
                q_pop = q_pops[isl]
                sampled_bits = np.zeros((island_size, self.n_bits), dtype=int)

                for i in range(island_size):
                    if self.evaluations_count_ >= self.total_budget:
                        break

                    probs = np.sin(q_pop[i]) ** 2
                    bits = (rng.random(self.n_bits) < probs).astype(int)

                    # Optional repair
                    if self.repair_func is not None:
                        bits = self.repair_func(bits)

                    sampled_bits[i] = bits
                    fit = float(fitness_func(bits))
                    self.evaluations_count_ += 1

                    if fit < p_best_fitness[isl][i]:
                        p_best_fitness[isl][i] = fit
                        p_best_bits[isl][i] = bits.copy()

                    if fit < island_best_fitness[isl]:
                        island_best_fitness[isl] = fit
                        island_best_bits[isl] = bits.copy()

                    if fit < global_best_fitness:
                        global_best_fitness = fit
                        global_best_bits = bits.copy()

                if self.evaluations_count_ >= self.total_budget:
                    break

                # 3. Quantum Rotation Gate update
                # Target: island best if using islands, else global best
                target_bits = (
                    island_best_bits[isl]
                    if (self.use_islands and island_best_bits[isl] is not None)
                    else global_best_bits
                )

                if target_bits is not None:
                    for i in range(island_size):
                        x = sampled_bits[i]
                        b = target_bits
                        # Han & Kim directional lookup table:
                        # x=0, b=1 -> rotate towards pi/2 (+rot_angle)
                        # x=1, b=0 -> rotate towards 0 (-rot_angle)
                        # x==b -> 0 (no perturbation on matching alleles)
                        direction = np.zeros(self.n_bits)
                        direction[(x == 0) & (b == 1)] = 1.0
                        direction[(x == 1) & (b == 0)] = -1.0
                        delta = direction * rot_angle
                        q_pop[i] = np.clip(q_pop[i] + delta, 0.01, math.pi / 2.0 - 0.01)

                # 4. Quantum NOT Mutation
                mut_mask = rng.random(q_pop.shape) < self.mutation_rate
                q_pop[mut_mask] = (math.pi / 2.0) - q_pop[mut_mask]

            # 5. Island Migration (ring topology across sub-populations)
            if self.use_islands and (gen % self.migration_interval == 0):
                for isl in range(num_islands):
                    next_isl = (isl + 1) % num_islands
                    worst_idx = int(np.argmax(p_best_fitness[next_isl]))
                    best_idx = int(np.argmin(p_best_fitness[isl]))
                    # Soft blend best individual of isl into worst of next_isl
                    q_pops[next_isl][worst_idx] = 0.5 * (
                        q_pops[next_isl][worst_idx] + q_pops[isl][best_idx]
                    )

            # 6. Memetic Local Search on Global Best
            if (
                self.use_memetic
                and (gen % self.memetic_interval == 0)
                and (global_best_bits is not None)
                and (self.evaluations_count_ < self.total_budget)
            ):
                cur_bits = global_best_bits.copy()
                cur_fit = global_best_fitness
                perm = rng.permutation(self.n_bits)

                for bit_idx in perm:
                    if self.evaluations_count_ >= self.total_budget:
                        break
                    cand = cur_bits.copy()
                    cand[bit_idx] = 1 - cand[bit_idx]
                    f = float(fitness_func(cand))
                    self.evaluations_count_ += 1

                    if f < cur_fit:
                        cur_bits = cand
                        cur_fit = f
                        global_best_bits = cur_bits.copy()
                        global_best_fitness = cur_fit

            if self.record_q_history:
                # Average probability sin^2(theta) across all islands and individuals
                all_angles = np.vstack(q_pops)
                mean_probs = np.mean(np.sin(all_angles) ** 2, axis=0)
                self.q_prob_history_.append(mean_probs.copy())

            self.convergence_curve_.append(global_best_fitness)

            if progress_callback:
                progress_callback(
                    min(len(self.convergence_curve_), self.generations),
                    self.generations,
                    global_best_fitness,
                )

        while len(self.convergence_curve_) < self.generations:
            self.convergence_curve_.append(global_best_fitness)
            if self.record_q_history and self.q_prob_history_:
                self.q_prob_history_.append(self.q_prob_history_[-1].copy())

        self.best_bits_ = global_best_bits
        self.best_fitness_ = global_best_fitness

        res_dict = {
            "best_bits": self.best_bits_,
            "best_fitness": self.best_fitness_,
            "convergence_curve": self.convergence_curve_,
            "evaluations": self.evaluations_count_,
        }
        if self.record_q_history:
            res_dict["q_prob_history"] = self.q_prob_history_
        return res_dict
