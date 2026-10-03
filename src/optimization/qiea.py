"""
Quantum-Inspired Evolutionary Algorithm (QIEA) for Combinatorial and Discrete Fleet Optimization.

Key Principles:
1. Q-bit probabilistic representation:
   Each quantum-inspired bit (Q-bit) is represented by an angle theta in [0, pi/2].
   The probability of observing state 1 is sin^2(theta), and state 0 is cos^2(theta).
2. Superposition Initialization:
   All angles are initialized to theta = pi / 4, conferring equal probability (0.50)
   of observing 0 or 1, maximizing initial exploratory entropy across the decision space.
3. Measurement / Collapse:
   In each generation, binary candidate solutions are sampled probabilistically
   from the Q-bit angular distributions.
4. Quantum Rotation Gate:
   Angles are incrementally updated toward the best observed solution using rotation
   gates Delta-theta, driving probabilistic convergence toward optimal hyper-planes.
5. Quantum NOT Mutation & Island Migration:
   Prevents premature entrapment in local optima by inverting Q-bit angles
   (theta -> pi/2 - theta) and synchronizing elite alleles periodically.
"""

from __future__ import annotations
import math
from typing import Callable, Dict, Any, List, Optional, Tuple
import numpy as np


class QIEA:
    """
    Quantum-Inspired Evolutionary Algorithm.
    Minimizes an objective function f(x) where x is a binary bitstring.
    """

    def __init__(
        self,
        n_bits: int,
        pop_size: int = 25,
        generations: int = 40,
        rotation_angle: float = 0.05,
        mutation_rate: float = 0.02,
        migration_interval: int = 10,
        random_seed: int = 42,
        initial_theta: Optional[float | np.ndarray] = None,
    ):
        self.n_bits = n_bits
        self.pop_size = pop_size
        self.generations = generations
        self.rotation_angle = rotation_angle
        self.mutation_rate = mutation_rate
        self.migration_interval = migration_interval
        self.random_seed = random_seed
        self.initial_theta = initial_theta

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

        Args:
            fitness_func: Function accepting binary array (shape (n_bits,)) and returning scalar cost.
            progress_callback: Optional callback(current_gen, total_gens, current_best_fitness).
            seed_bits: Optional binary solution to seed global best.

        Returns:
            Dictionary containing best_bits, best_fitness, convergence_curve, evaluations.
        """
        rng = np.random.default_rng(self.random_seed)
        self.evaluations_count_ = 0
        self.convergence_curve_ = []

        # 1. Initialize Q-bit population: theta = pi / 4 (superposition) or custom initial angles
        # Dimensions: [pop_size, n_bits]
        if self.initial_theta is None:
            q_pop = np.full((self.pop_size, self.n_bits), math.pi / 4.0)
        elif isinstance(self.initial_theta, (int, float)):
            q_pop = np.full((self.pop_size, self.n_bits), float(self.initial_theta))
        else:
            # Array-like of shape (n_bits,)
            init_arr = np.asarray(self.initial_theta, dtype=float)
            q_pop = np.tile(init_arr, (self.pop_size, 1))

        # Track population binary observations and individual bests
        p_best_bits = np.zeros((self.pop_size, self.n_bits), dtype=int)
        p_best_fitness = np.full(self.pop_size, float("inf"))

        global_best_bits = None
        global_best_fitness = float("inf")

        if seed_bits is not None:
            seed_fitness = float(fitness_func(seed_bits))
            self.evaluations_count_ += 1
            global_best_fitness = seed_fitness
            global_best_bits = seed_bits.copy()

        for gen in range(self.generations):
            gen_best_fitness = float("inf")
            gen_best_bits = None

            # 2. Measurement: observe binary solutions from Q-bits
            for i in range(self.pop_size):
                probs = np.sin(q_pop[i]) ** 2
                observed_bits = (rng.random(self.n_bits) < probs).astype(int)

                # Evaluate fitness
                fitness = float(fitness_func(observed_bits))
                self.evaluations_count_ += 1

                # Update individual best
                if fitness < p_best_fitness[i]:
                    p_best_fitness[i] = fitness
                    p_best_bits[i] = observed_bits.copy()

                # Update generation best
                if fitness < gen_best_fitness:
                    gen_best_fitness = fitness
                    gen_best_bits = observed_bits.copy()

                # Update global best
                if fitness < global_best_fitness:
                    global_best_fitness = fitness
                    global_best_bits = observed_bits.copy()

            self.convergence_curve_.append(global_best_fitness)

            if progress_callback:
                progress_callback(gen + 1, self.generations, global_best_fitness)

            # 3. Quantum Rotation Gate Update (Vectorized NumPy acceleration)
            # If target bit is 1, rotate toward pi/2; if 0, rotate toward 0
            target_bits = global_best_bits
            delta = np.where(target_bits == 1, self.rotation_angle, -self.rotation_angle)
            q_pop = np.clip(q_pop + delta, 0.0, math.pi / 2.0)

            # 4. Quantum NOT Mutation: invert superposition with small probability
            mut_mask = rng.random(q_pop.shape) < self.mutation_rate
            q_pop[mut_mask] = (math.pi / 2.0) - q_pop[mut_mask]

            # 5. Migration: Periodic alignment of worst individual with best individual's Q-angles
            if (gen + 1) % self.migration_interval == 0:
                worst_idx = int(np.argmax(p_best_fitness))
                best_idx = int(np.argmin(p_best_fitness))
                # Soft migration: blend worst individual toward best Q-angles
                q_pop[worst_idx] = 0.5 * (q_pop[worst_idx] + q_pop[best_idx])

        self.best_bits_ = global_best_bits
        self.best_fitness_ = global_best_fitness

        return {
            "best_bits": self.best_bits_,
            "best_fitness": self.best_fitness_,
            "convergence_curve": self.convergence_curve_,
            "evaluations": self.evaluations_count_,
        }
