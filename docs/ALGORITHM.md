# Quantum-Inspired Evolutionary Algorithm (QIEA) Specification

## 1. Algorithmic Background & Paradigm

The Quantum-Inspired Evolutionary Algorithm (QIEA) is a **classical probabilistic meta-heuristic** designed to solve high-dimensional discrete and combinatorial optimization problems on standard CPU architectures.

> **CRITICAL DISCLAIMER:** "Quantum-inspired" refers strictly to classical algorithmic concepts borrowing probabilistic principles from quantum computing (e.g., superposition-like state exploration, Q-bit angular representation, and rotation gate transformation operators). **No quantum hardware, Qiskit libraries, or quantum simulators are used.** It runs entirely on standard classical computer processors.

---

## 2. Quantum Bit (Q-Bit) Representation

In standard classical genetic algorithms, a candidate gene is represented by a deterministic binary bit:

$$x_j \in \{0, 1\}$$

In QIEA, a quantum-inspired bit (Q-bit) $q_j$ is defined by a probability amplitude pair $(\alpha_j, \beta_j)$:

$$|q_j\rangle = \alpha_j |0\rangle + \beta_j |1\rangle$$

satisfying the normalization condition:

$$|\alpha_j|^2 + |\beta_j|^2 = 1$$

To enforce this normalization intrinsically without numerical drift, QIEA parameterizes each Q-bit by a single rotation phase angle $\theta_j \in [0, \pi/2]$:

$$\alpha_j = \cos(\theta_j), \quad \beta_j = \sin(\theta_j)$$

Hence, the probability $P(x_j = 1)$ of observing a classical bit value 1 upon measurement is:

$$P(x_j = 1) = \sin^2(\theta_j)$$

$$P(x_j = 0) = \cos^2(\theta_j)$$

### Superposition Initialization
At generation $t = 0$, all Q-bit angles are initialized to:

$$\theta_j = \frac{\pi}{4}$$

Since $\cos^2(\pi/4) = \sin^2(\pi/4) = 0.50$, every Q-bit initially represents an **equal superposition** state. A single Q-bit chromosome of length $L$ implicitly represents all $2^L$ possible binary configurations with uniform probability distribution, maximizing initial exploratory entropy across the decision hyperspace.

For sparse combinatorial resource allocation (e.g. vessel assignments where most routes only deploy 1 or 2 vessels), allocation bits can be initialized to $\theta_j = \pi/8$, conferring an initial expectation $\sin^2(\pi/8) \approx 0.146$ to promote sparse vessel deployment while preserving quantum rotation flexibility.

---

## 3. Problem Encoding & Chromosome Structure

The platform optimizes fleet deployment across $R$ corridors, $O$ candidate vessel-fuel configurations, and $P$ port terminals.

A solution is encoded as a binary bitstring $\mathbf{x} \in \{0, 1\}^L$:

1. **Vessel Allocations ($2 \times O \times R$ bits):**  
   Each candidate pair $(o, r)$ receives 2 binary bits, decoded into integer $n_{o, r} \in \{0, 1, 2, 3\}$ representing the number of vessels deployed.
2. **Route Cruising Speeds ($3 \times R$ bits):**  
   Each route receives 3 binary bits, decoded into an integer $s_r \in \{0, \dots, 7\}$ mapped linearly to discrete cruising speeds between $V_{\min}$ and $V_{\max}(r)$.
3. **Port Shore Power Cold-Ironing ($P$ bits):**  
   Each port terminal receives 1 binary bit indicating whether cold ironing is utilized when berthed ($1 = \text{Yes}, 0 = \text{No}$).

Total chromosome length:

$$L = 2(O \cdot R) + 3R + P$$

For the 5-route feeder network ($O=8, R=5, P=6$):

$$L = 2(8 \times 5) + 3(5) + 6 = 80 + 15 + 6 = 101 \text{ bits}$$

---

## 4. Quantum Rotation Gate Update Rule

In each generation, candidate binary solutions $\mathbf{x}_i$ are observed by sampling $r \sim \mathcal{U}(0, 1)$:

$$x_{i, j} = \begin{cases} 1 & \text{if } r < \sin^2(\theta_{i, j}) \\ 0 & \text{otherwise} \end{cases}$$

After evaluating the fitness of all individuals, the global best solution $\mathbf{b}^* = (b^*_1, b^*_2, \dots, b^*_L)$ is identified. Each individual's Q-bit angles are updated toward the global best solution using a **directional quantum rotation gate** $U(\Delta\theta)$:

$$\begin{bmatrix} \cos(\theta'_{i, j}) \\ \sin(\theta'_{i, j}) \end{bmatrix} = \begin{bmatrix} \cos(\Delta\theta_{i, j}) & -\sin(\Delta\theta_{i, j}) \\ \sin(\Delta\theta_{i, j}) & \cos(\Delta\theta_{i, j}) \end{bmatrix} \begin{bmatrix} \cos(\theta_{i, j}) \\ \sin(\theta_{i, j}) \end{bmatrix}$$

which simplifies in angle space to:

$$\theta_{i, j}^{(t+1)} = \theta_{i, j}^{(t)} + \Delta\theta_{i, j}$$

### Directional Rotation Lookup Table

| Observed Bit $x_{i, j}$ | Best Bit $b^*_j$ | $f(\mathbf{x}_i) \ge f(\mathbf{b}^*)$ | Rotation Angle $\Delta\theta_{i, j}$ | Boundary Enforcement |
| :---: | :---: | :---: | :---: | :---: |
| 0 | 1 | True (current is worse) | $+\Delta\theta_0$ | $\min(\pi/2, \theta + \Delta\theta)$ |
| 1 | 0 | True (current is worse) | $-\Delta\theta_0$ | $\max(0, \theta - \Delta\theta)$ |
| 0 | 0 | - | $0$ | None |
| 1 | 1 | - | $0$ | None |

Default step size $\Delta\theta_0 = 0.05 \text{ rad} \approx 2.86^\circ$.

---

## 5. Quantum Mutation & Island Migration

To prevent premature gene collapse and stagnation in local minima:

1. **Quantum NOT Inversion Mutation:**  
   With probability $p_m \approx 0.02$, a Q-bit angle is flipped across the superposition bisector:
   $$\theta_{i, j} \leftarrow \frac{\pi}{2} - \theta_{i, j}$$
   This transforms a state with $P(1) = p$ into $P(1) = 1 - p$.

2. **Periodic Allele Migration:**  
   Every $H = 10$ generations, the worst individual's Q-angles are softly blended toward the global elite Q-angles:
   $$\vec{\theta}_{\text{worst}} \leftarrow 0.5 \left(\vec{\theta}_{\text{worst}} + \vec{\theta}_{\text{best}}\right)$$

---

## 6. Algorithmic Pseudocode

```text
Algorithm: Quantum-Inspired Evolutionary Algorithm (QIEA)
Input:
  pop_size: Population size M
  generations: Maximum iterations G
  rotation_angle: Delta-theta step size (e.g. 0.05 rad)
  mutation_rate: Quantum NOT probability p_m (e.g. 0.02)
  migration_interval: Allele sync frequency H (e.g. 10)
  fitness_func: Objective evaluator f(x) -> Real

Output:
  b_best: Optimal binary bitstring
  f_best: Minimum penalized objective score

1: Initialize Q-bit population Q = [theta_{i, j}] of size M x L
   where theta_{i, j} = pi / 4  (or pi / 8 for allocation bits)
2: Initialize global best fitness f_best = infinity, b_best = null
3: For generation t = 1 to G do:
4:     For each individual i = 1 to M do:
5:         Sample binary vector x_i from sin^2(theta_{i, j})
6:         Evaluate fitness f_i = fitness_func(x_i)
7:         If f_i < f_best then:
8:             f_best = f_i
9:             b_best = x_i
10:        End If
11:    End For
12:    Record generation convergence: history[t] = f_best
13:    // Apply Quantum Rotation Gate
14:    For each individual i = 1 to M do:
15:        For each bit j = 1 to L do:
16:            If b_best[j] == 1 and theta_{i, j} < pi / 2 then:
17:                theta_{i, j} = min(pi / 2, theta_{i, j} + rotation_angle)
18:            Else if b_best[j] == 0 and theta_{i, j} > 0 then:
19:                theta_{i, j} = max(0, theta_{i, j} - rotation_angle)
20:            End If
21:            // Quantum NOT Mutation
22:            If random(0, 1) < mutation_rate then:
23:                theta_{i, j} = (pi / 2) - theta_{i, j}
24:            End If
25:        End For
26:    End For
27:    // Periodic Migration
28:    If t mod migration_interval == 0 then:
29:        Blend worst individual's angles toward best individual's angles
30:    End If
31: End For
32: Return b_best, f_best, history
```
