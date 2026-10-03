import sys, os
sys.path.insert(0, os.path.abspath("."))
import numpy as np
from src.optimization.problem import FleetOptimizationProblem

p = FleetOptimizationProblem()
print("Total routes:", len(p.route_keys))
for r_k in p.route_keys:
    print(r_k, p.config["routes"][r_k])

print("\nVessel availability:", {k: v.get("fleet_available", 6) for k, v in p.config["vessel_types"].items()})

# Let's test naive assignments
# HFO options: 0 (small), 2 (handymax), 5 (sub_panamax)
for spd in range(8):
    bits = np.zeros(p.n_bits, dtype=int)
    alloc = np.zeros((8, 5), dtype=int)
    alloc[2, 0] = 2  # R1: 2 handymax
    alloc[2, 1] = 1  # R2: 1 handymax (was 1 small)
    alloc[2, 2] = 1  # R3: 1 handymax (or check what meets demand)
    alloc[0, 2] = 1  # R3: 1 small
    alloc[0, 3] = 1  # R4: 1 small
    alloc[5, 4] = 3  # R5: 3 sub-panamax
    
    idx = 0
    for o in range(8):
        for r in range(5):
            val = alloc[o, r]
            bits[idx] = (val >> 1) & 1
            bits[idx+1] = val & 1
            idx += 2
    for r in range(5):
        bits[idx] = (spd >> 2) & 1
        bits[idx+1] = (spd >> 1) & 1
        bits[idx+2] = spd & 1
        idx += 3
        
    res = p.evaluate(bits)
    print(f"Speed idx {spd} ({10.5 + spd} kn): Feasible={res['is_feasible']}, CI={res['carbon_intensity_g_tnm']:.2f}, Cost=${res['total_operating_cost_usd']/1e6:.2f}M, Violations={res['total_violation_score']:.2f}")
    if spd in [1, 2]:
        for r_k, rd in res['route_details'].items():
            print(f"  {r_k}: cap={rd['annual_capacity_teu']}, dem={rd['annual_demand_teu']}, freq={rd['sailings_per_week']:.2f}, rel={rd['reliability']:.2f}")
