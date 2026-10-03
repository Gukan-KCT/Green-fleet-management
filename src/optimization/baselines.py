"""
Baseline Optimization Algorithms:
1. Binary Genetic Algorithm (GA) with tournament selection, uniform crossover, bit-flip mutation, and elitism.
2. Particle Swarm Optimization (PSO) with continuous positions mapped to binary bitstrings.
3. Uniform Random Search baseline.

All algorithms conform to the exact same budget and interface:
`optimize(fitness_func) -> Dict[str, Any]`
"""

from __future__ import annotations
import math
from typing import Callable, Dict, Any, List, Optional
import numpy as np


class BinaryGeneticAlgorithm:
    """
    Standard Canonical Binary Genetic Algorithm.
    """

    def __init__(
        self,
        n_bits: int,
        pop_size: int = 25,
        generations: int = 40,
        crossover_rate: float = 0.85,
        mutation_rate: Optional[float] = None,
        tournament_size: int = 3,
        random_seed: int = 42,
    ):
        self.n_bits = n_bits
        self.pop_size = pop_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate if mutation_rate is not None else (1.0 / n_bits)
        self.tournament_size = tournament_size
        self.random_seed = random_seed

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
        rng = np.random.default_rng(self.random_seed)
        self.evaluations_count_ = 0
        self.convergence_curve_ = []

        # Initialize binary population
        pop = rng.integers(0, 2, size=(self.pop_size, self.n_bits))
        if seed_bits is not None:
            pop[0] = seed_bits.copy()

        fitnesses = np.full(self.pop_size, float("inf"))

        global_best_bits = None
        global_best_fitness = float("inf")

        for i in range(self.pop_size):
            fitnesses[i] = float(fitness_func(pop[i]))
            self.evaluations_count_ += 1
            if fitnesses[i] < global_best_fitness:
                global_best_fitness = fitnesses[i]
                global_best_bits = pop[i].copy()

        self.convergence_curve_.append(global_best_fitness)

        for gen in range(1, self.generations):
            new_pop = []

            # 1. Elitism: preserve top solution
            best_idx = int(np.argmin(fitnesses))
            new_pop.append(pop[best_idx].copy())

            # 2. Reproduction loop
            while len(new_pop) < self.pop_size:
                # Tournament selection for parent 1
                tourn1 = rng.choice(self.pop_size, size=self.tournament_size, replace=False)
                p1_idx = tourn1[np.argmin(fitnesses[tourn1])]
                p1 = pop[p1_idx]

                # Tournament selection for parent 2
                tourn2 = rng.choice(self.pop_size, size=self.tournament_size, replace=False)
                p2_idx = tourn2[np.argmin(fitnesses[tourn2])]
                p2 = pop[p2_idx]

                # Crossover
                if rng.random() < self.crossover_rate:
                    mask = rng.random(self.n_bits) < 0.5
                    c1 = np.where(mask, p1, p2)
                    c2 = np.where(mask, p2, p1)
                else:
                    c1, c2 = p1.copy(), p2.copy()

                # Mutation
                for c in [c1, c2]:
                    mut_mask = rng.random(self.n_bits) < self.mutation_rate
                    c[mut_mask] = 1 - c[mut_mask]
                    new_pop.append(c)
                    if len(new_pop) >= self.pop_size:
                        break

            pop = np.array(new_pop)

            # Evaluate new population (guaranteeing exact pop_size evaluations per generation)
            for i in range(self.pop_size):
                fitnesses[i] = float(fitness_func(pop[i]))
                self.evaluations_count_ += 1
                if fitnesses[i] < global_best_fitness:
                    global_best_fitness = fitnesses[i]
                    global_best_bits = pop[i].copy()

            self.convergence_curve_.append(global_best_fitness)

            if progress_callback:
                progress_callback(gen + 1, self.generations, global_best_fitness)

        self.best_bits_ = global_best_bits
        self.best_fitness_ = global_best_fitness

        return {
            "best_bits": self.best_bits_,
            "best_fitness": self.best_fitness_,
            "convergence_curve": self.convergence_curve_,
            "evaluations": self.evaluations_count_,
        }


class ParticleSwarmOptimization:
    """
    Binary Particle Swarm Optimization using continuous position thresholding
    with dynamically decaying inertia weight and velocity clipping.
    """

    def __init__(
        self,
        n_bits: int,
        swarm_size: int = 25,
        generations: int = 40,
        w_max: float = 0.90,
        w_min: float = 0.40,
        c1: float = 1.60,
        c2: float = 1.60,
        random_seed: int = 42,
    ):
        self.n_bits = n_bits
        self.swarm_size = swarm_size
        self.generations = generations
        self.w_max = w_max
        self.w_min = w_min
        self.c1 = c1
        self.c2 = c2
        self.random_seed = random_seed

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
        rng = np.random.default_rng(self.random_seed)
        self.evaluations_count_ = 0
        self.convergence_curve_ = []

        # Positions in [0, 1]
        positions = rng.uniform(0.0, 1.0, size=(self.swarm_size, self.n_bits))
        if seed_bits is not None:
            positions[0] = np.where(seed_bits == 1, 0.85, 0.15)

        velocities = rng.uniform(-0.15, 0.15, size=(self.swarm_size, self.n_bits))

        pbest_positions = positions.copy()
        pbest_fitness = np.full(self.swarm_size, float("inf"))

        gbest_position = None
        gbest_bits = None
        gbest_fitness = float("inf")

        for gen in range(self.generations):
            # Dynamic inertia weight decay
            w_cur = self.w_max - (self.w_max - self.w_min) * (gen / max(1, self.generations - 1))

            for i in range(self.swarm_size):
                # Map continuous position to binary bits via threshold
                binary_sol = (positions[i] >= 0.5).astype(int)
                fitness = float(fitness_func(binary_sol))
                self.evaluations_count_ += 1

                if fitness < pbest_fitness[i]:
                    pbest_fitness[i] = fitness
                    pbest_positions[i] = positions[i].copy()

                if fitness < gbest_fitness:
                    gbest_fitness = fitness
                    gbest_position = positions[i].copy()
                    gbest_bits = binary_sol.copy()

            self.convergence_curve_.append(gbest_fitness)

            if progress_callback:
                progress_callback(gen + 1, self.generations, gbest_fitness)

            # Update velocity and positions
            r1 = rng.random((self.swarm_size, self.n_bits))
            r2 = rng.random((self.swarm_size, self.n_bits))

            velocities = (
                w_cur * velocities
                + self.c1 * r1 * (pbest_positions - positions)
                + self.c2 * r2 * (gbest_position - positions)
            )
            # Clip velocities to avoid boundary trapping
            velocities = np.clip(velocities, -0.35, 0.35)
            positions = np.clip(positions + velocities, 0.0, 1.0)

        self.best_bits_ = gbest_bits
        self.best_fitness_ = gbest_fitness

        return {
            "best_bits": self.best_bits_,
            "best_fitness": self.best_fitness_,
            "convergence_curve": self.convergence_curve_,
            "evaluations": self.evaluations_count_,
        }


class RandomSearch:
    """
    Uniform Random Search baseline with identical evaluation budget.
    """

    def __init__(
        self,
        n_bits: int,
        evaluations_per_generation: int = 25,
        generations: int = 40,
        random_seed: int = 42,
    ):
        self.n_bits = n_bits
        self.evaluations_per_generation = evaluations_per_generation
        self.generations = generations
        self.random_seed = random_seed

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
        rng = np.random.default_rng(self.random_seed)
        self.evaluations_count_ = 0
        self.convergence_curve_ = []

        global_best_bits = None
        global_best_fitness = float("inf")

        if seed_bits is not None:
            seed_fitness = float(fitness_func(seed_bits))
            self.evaluations_count_ += 1
            global_best_fitness = seed_fitness
            global_best_bits = seed_bits.copy()

        for gen in range(self.generations):
            for _ in range(self.evaluations_per_generation):
                candidate = rng.integers(0, 2, size=self.n_bits)
                fitness = float(fitness_func(candidate))
                self.evaluations_count_ += 1

                if fitness < global_best_fitness:
                    global_best_fitness = fitness
                    global_best_bits = candidate.copy()

            self.convergence_curve_.append(global_best_fitness)

            if progress_callback:
                progress_callback(gen + 1, self.generations, global_best_fitness)

        self.best_bits_ = global_best_bits
        self.best_fitness_ = global_best_fitness

        return {
            "best_bits": self.best_bits_,
            "best_fitness": self.best_fitness_,
            "convergence_curve": self.convergence_curve_,
            "evaluations": self.evaluations_count_,
        }
