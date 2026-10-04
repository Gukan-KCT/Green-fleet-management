"""
Fleet Optimization Problem Formulation.

Decision Variables (encoded in binary chromosome):
1. Vessel allocation: Integer in [0, max_vessels] for each (vessel_type, fuel) option on each route.
2. Route cruising speed: Discretized index (0 to 7) mapped to [v_min, speed_cap].
3. Shore power usage flag: Boolean bit for each port in the network.

Objectives:
1. Total Fuel Consumption (Energy-equivalent, Gigajoules GJ)
2. Total Annual Operating Cost ($ USD: fuel + time charter/fixed + port calls + shore electricity + carbon tax)
3. Total Annual Lifecycle GHG Emissions (tonnes CO2e Well-to-Wake)

Constraints (with individual violation metrics and penalty barrier):
- Cargo Demand: Delivered capacity >= annual route TEU demand.
- Service Frequency: Sailings per week >= minimum required frequency.
- Schedule Reliability: Operational reliability index >= threshold (0.80).
- Fleet Availability: Total vessels deployed of type v <= available fleet count.
- Speed Limits: Vessel v_min <= V <= route speed cap.
- Fuel Availability: Fuel bunkering supported at origin or destination port.
- Carbon Intensity: Fleet carbon intensity (gCO2e / t-nm) <= regulatory cap.
  (Simplified proxy, explicitly distinct from official IMO Carbon Intensity Indicator CII).
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from src.models.physics import (
    load_config,
    calculate_leg_fuel_conventional,
    calculate_alternative_fuel_mass,
    calculate_fuel_energy_gj,
    calculate_emissions,
    get_fuel_price_usd_per_tonne,
    calculate_usable_capacity_teu,
    calculate_schedule_reliability,
    calculate_berth_energy_and_emissions,
)
from src.analysis.fuels import VESSEL_FUEL_COMPATIBILITY


DEFAULT_CANDIDATE_OPTIONS = [
    {"vessel": "small_feeder", "fuel": "HFO", "pathway": "fossil"},
    {"vessel": "small_feeder", "fuel": "Methanol", "pathway": "green"},
    {"vessel": "handymax_feeder", "fuel": "HFO", "pathway": "fossil"},
    {"vessel": "handymax_feeder", "fuel": "LNG", "pathway": "fossil"},
    {"vessel": "handymax_feeder", "fuel": "Methanol", "pathway": "green"},
    {"vessel": "sub_panamax_feeder", "fuel": "HFO", "pathway": "fossil"},
    {"vessel": "sub_panamax_feeder", "fuel": "LNG", "pathway": "fossil"},
    {"vessel": "panamax_feeder", "fuel": "Ammonia", "pathway": "green"},
]


class FleetOptimizationProblem:
    """
    Formulates and evaluates fleet deployment schedules against multiple objectives
    and operational/regulatory constraints.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        candidate_options: Optional[List[Dict[str, str]]] = None,
        weights: Optional[Dict[str, float]] = None,
        routes_override: Optional[Dict[str, Any]] = None,
        fuel_price_multiplier: float = 1.0,
        demand_multiplier: float = 1.0,
        weather_multiplier: float = 1.0,
        speed_cap_delta: float = 0.0,
        shore_power_forced: Optional[bool] = None,
        carbon_intensity_cap: Optional[float] = None,
        supply_cap_ratio: Optional[float] = None,
        use_gray_code: Optional[bool] = None,
    ):
        self.config = config or load_config()
        self.options = candidate_options or DEFAULT_CANDIDATE_OPTIONS
        self.routes = routes_override or self.config["routes"]
        self.route_keys = list(self.routes.keys())
        self.port_keys = list(self.config["ports"].keys())

        # Sensitivity multipliers
        self.fuel_price_multiplier = fuel_price_multiplier
        self.demand_multiplier = demand_multiplier
        self.weather_multiplier = weather_multiplier
        self.speed_cap_delta = speed_cap_delta
        self.shore_power_forced = shore_power_forced

        opt_cfg = self.config["optimization"]
        self.use_gray_code = (
            use_gray_code
            if use_gray_code is not None
            else bool(opt_cfg.get("use_gray_code", False))
        )
        self.penalty_weight = float(opt_cfg.get("penalty_weight_large", 10000.0))
        self.max_vessels_per_option = int(opt_cfg.get("max_vessels_per_option", 4))
        self.speed_levels_count = int(opt_cfg.get("speed_levels_count", 8))
        self.carbon_intensity_cap = (
            carbon_intensity_cap
            if carbon_intensity_cap is not None
            else float(opt_cfg.get("carbon_intensity_cap_g_per_tonne_nm", 18.0))
        )
        self.supply_cap_ratio = (
            supply_cap_ratio
            if supply_cap_ratio is not None
            else opt_cfg.get("supply_cap_ratio", None)
        )
        if self.supply_cap_ratio is not None:
            self.supply_cap_ratio = float(self.supply_cap_ratio)
        self.reliability_threshold = float(opt_cfg.get("reliability_min_threshold", 0.70))
        self.operating_days_year = float(self.config["general"].get("days_per_year", 350.0))
        self.carbon_tax_rate = float(self.config["general"].get("carbon_price_usd_per_tonne", 80.0))

        # Objective normalization references (approximate scaling factors for unit variance)
        self.norm_fuel_gj = 500000.0
        self.norm_cost_usd = 25000000.0
        self.norm_emissions_t = 35000.0

        # Weights
        w = weights or opt_cfg.get("default_weights", {"fuel": 0.3, "cost": 0.4, "emissions": 0.3})
        w_sum = w.get("fuel", 0.3) + w.get("cost", 0.4) + w.get("emissions", 0.3)
        self.w_fuel = w.get("fuel", 0.3) / w_sum
        self.w_cost = w.get("cost", 0.4) / w_sum
        self.w_emissions = w.get("emissions", 0.3) / w_sum

        # Calculate chromosome bit layout
        # 1. Allocation bits: 2 bits per (option, route) -> values 0, 1, 2, 3
        self.n_alloc_bits = 2 * len(self.options) * len(self.route_keys)
        # 2. Speed bits: 3 bits per route (8 levels)
        self.n_speed_bits = 3 * len(self.route_keys)
        # 3. Shore power bits: 1 bit per port
        self.n_port_bits = len(self.port_keys)

        self.n_bits = self.n_alloc_bits + self.n_speed_bits + self.n_port_bits

    def get_initial_q_angles(self) -> np.ndarray:
        """
        Return initial Q-bit angles for problem structure:
        - Allocation bits: pi / 8 (representing sparse initial vessel deployments)
        - Speed bits & Shore power bits: pi / 4 (equal superposition)
        """
        angles = np.full(self.n_bits, math.pi / 4.0)
        angles[: self.n_alloc_bits] = math.pi / 8.0
        return angles

    def decode_solution(
        self, bits: np.ndarray
    ) -> Tuple[np.ndarray, Dict[str, float], Dict[str, bool]]:
        """
        Decode a binary chromosome array into:
        1. allocations: matrix [num_options, num_routes] of vessel counts
        2. speeds: dict of route_id -> speed_knots
        3. shore_power: dict of port_id -> bool
        """
        idx = 0
        n_opts = len(self.options)
        n_routes = len(self.route_keys)

        # 1. Decode vessel allocations
        allocations = np.zeros((n_opts, n_routes), dtype=int)
        for o in range(n_opts):
            for r in range(n_routes):
                b0 = bits[idx]
                b1 = bits[idx + 1]
                idx += 2
                if self.use_gray_code:
                    val = (b0 << 1) | (b0 ^ b1)
                else:
                    val = (b0 << 1) | b1
                allocations[o, r] = min(val, self.max_vessels_per_option)

        # 2. Decode speeds per route
        speeds = {}
        for r_idx, r_key in enumerate(self.route_keys):
            r_cfg = self.routes[r_key]
            if self.use_gray_code:
                c0 = bits[idx]
                c1 = c0 ^ bits[idx + 1]
                c2 = c1 ^ bits[idx + 2]
                speed_bits = (c0 << 2) | (c1 << 1) | c2
            else:
                speed_bits = (bits[idx] << 2) | (bits[idx + 1] << 1) | bits[idx + 2]
            idx += 3

            # Map speed level to [min_speed, max_speed]
            cap = float(r_cfg.get("speed_cap_knots", 18.0)) + self.speed_cap_delta
            v_min = 11.0
            v_max = max(v_min + 1.0, cap)
            frac = speed_bits / (self.speed_levels_count - 1.0)
            speeds[r_key] = round(v_min + frac * (v_max - v_min), 2)

        # 3. Decode shore power per port
        shore_power = {}
        for p_idx, p_key in enumerate(self.port_keys):
            if self.shore_power_forced is not None:
                shore_power[p_key] = self.shore_power_forced
            else:
                shore_power[p_key] = bool(bits[idx] == 1)
            idx += 1

        return allocations, speeds, shore_power

    def encode_solution(
        self,
        allocations: np.ndarray,
        speeds: Dict[str, float],
        shore_power: Dict[str, bool],
    ) -> np.ndarray:
        """
        Encode decisions (allocations, speeds, shore_power) into a binary chromosome.
        Respects self.use_gray_code setting.
        """
        bits = np.zeros(self.n_bits, dtype=int)
        idx = 0
        n_opts = len(self.options)
        n_routes = len(self.route_keys)

        for o in range(n_opts):
            for r in range(n_routes):
                val = int(allocations[o, r])
                if self.use_gray_code:
                    g = val ^ (val >> 1)
                    bits[idx] = (g >> 1) & 1
                    bits[idx + 1] = g & 1
                else:
                    bits[idx] = (val >> 1) & 1
                    bits[idx + 1] = val & 1
                idx += 2

        for r_key in self.route_keys:
            r_cfg = self.routes[r_key]
            cap = float(r_cfg.get("speed_cap_knots", 18.0)) + self.speed_cap_delta
            v_min = 11.0
            v_max = max(v_min + 1.0, cap)
            spd = float(speeds.get(r_key, v_min))
            frac = max(0.0, min(1.0, (spd - v_min) / max(1e-4, v_max - v_min)))
            spd_idx = int(round(frac * (self.speed_levels_count - 1.0)))
            spd_idx = max(0, min(self.speed_levels_count - 1, spd_idx))

            if self.use_gray_code:
                g = spd_idx ^ (spd_idx >> 1)
                bits[idx] = (g >> 2) & 1
                bits[idx + 1] = (g >> 1) & 1
                bits[idx + 2] = g & 1
            else:
                bits[idx] = (spd_idx >> 2) & 1
                bits[idx + 1] = (spd_idx >> 1) & 1
                bits[idx + 2] = spd_idx & 1
            idx += 3

        for p_key in self.port_keys:
            bits[idx] = 1 if shore_power.get(p_key, False) else 0
            idx += 1

        return bits

    def repair_solution(self, bits: np.ndarray) -> np.ndarray:
        """
        Constraint repair operator:
        1. Enforces fleet availability limits by trimming allocations from routes with excess vessels.
        2. Reduces route speed in severe weather to satisfy operational schedule reliability.
        """
        allocations, speeds, shore_power = self.decode_solution(bits)
        modified = False

        # 1. Enforce fleet availability
        used_by_type = {}
        for o_idx, opt in enumerate(self.options):
            v_t = opt["vessel"]
            used_by_type[v_t] = used_by_type.get(v_t, 0) + int(np.sum(allocations[o_idx, :]))

        for v_t, count in used_by_type.items():
            avail = int(self.config["vessel_types"][v_t].get("fleet_available", 6))
            while count > avail:
                opt_indices = [i for i, opt in enumerate(self.options) if opt["vessel"] == v_t]
                max_v, best_o, best_r = 0, None, None
                for o in opt_indices:
                    for r in range(len(self.route_keys)):
                        if allocations[o, r] > max_v:
                            max_v = allocations[o, r]
                            best_o, best_r = o, r
                if best_o is not None and max_v > 0:
                    allocations[best_o, best_r] -= 1
                    count -= 1
                    modified = True
                else:
                    break

        # 2. Reliability repair
        for r_key in self.route_keys:
            r_cfg = self.routes[r_key]
            w = float(r_cfg.get("weather_severity", 0.3)) * self.weather_multiplier
            if w > 0.32 and speeds[r_key] > 13.0:
                speeds[r_key] = 11.5
                modified = True

        if not modified:
            return bits
        return self.encode_solution(allocations, speeds, shore_power)

    def evaluate(self, bits: np.ndarray) -> Dict[str, Any]:
        """
        Evaluate full operational schedule. Computes all objectives, constraint checks,
        and composite penalized fitness.
        """
        allocations, speeds, shore_power = self.decode_solution(bits)

        total_fuel_gj = 0.0
        total_fuel_tonnes_hfo_eq = 0.0
        total_operating_cost = 0.0
        total_emissions_co2e = 0.0
        total_transport_work_tnm = 0.0
        total_cargo_delivered_teu = 0.0

        constraint_violations = {
            "demand": 0.0,
            "frequency": 0.0,
            "reliability": 0.0,
            "vessel_availability": 0.0,
            "fuel_bunkering": 0.0,
            "vessel_compatibility": 0.0,
            "carbon_intensity": 0.0,
            "supply_cap": 0.0,
        }

        # Track fleet usage across routes by vessel type
        vessels_used_by_type: Dict[str, int] = {}
        for o_idx, opt in enumerate(self.options):
            v_type = opt["vessel"]
            vessels_used_by_type[v_type] = vessels_used_by_type.get(v_type, 0) + int(
                np.sum(allocations[o_idx, :])
            )

        # 1. Constraint: Fleet Availability
        for v_type, used_count in vessels_used_by_type.items():
            avail = int(self.config["vessel_types"][v_type].get("fleet_available", 6))
            if used_count > avail:
                constraint_violations["vessel_availability"] += float(used_count - avail)

        # Route-by-route evaluations
        total_ttw_emissions = 0.0
        total_wtt_emissions = 0.0
        total_slip_emissions = 0.0
        total_berth_emissions = 0.0
        route_details = {}

        for r_idx, r_key in enumerate(self.route_keys):
            r_cfg = self.routes[r_key]
            dist_nm = float(r_cfg["distance_nm"])
            rt_distance = 2.0 * dist_nm
            annual_demand = float(r_cfg["annual_demand_teu"]) * self.demand_multiplier
            min_freq = float(r_cfg.get("min_sailings_per_week", 1.0))
            weather = max(0.0, min(1.0, float(r_cfg.get("weather_severity", 0.3)) * self.weather_multiplier))
            speed = speeds[r_key]

            orig_port = self.config["ports"][r_cfg["origin"]]
            dest_port = self.config["ports"][r_cfg["destination"]]
            berth_hours_rt = float(orig_port["berth_hours_avg"]) + float(dest_port["berth_hours_avg"])

            # Round trip transit time (hours)
            sea_hours = rt_distance / speed
            rt_hours = sea_hours + berth_hours_rt
            max_trips_per_vessel = (self.operating_days_year * 24.0) / rt_hours

            route_cargo_cap = 0.0
            route_cargo_tonnes_cap = 0.0
            route_annual_trips = 0.0
            route_reliabilities = []
            route_assigned_vessels = 0
            route_ttw_emiss = 0.0
            route_wtt_emiss = 0.0
            route_slip_emiss = 0.0
            route_berth_emiss = 0.0

            for o_idx, opt in enumerate(self.options):
                n_vessels = allocations[o_idx, r_idx]
                if n_vessels == 0:
                    continue

                route_assigned_vessels += n_vessels
                v_type = opt["vessel"]
                fuel_type = opt["fuel"]
                pathway = opt.get("pathway", "default")
                v_cfg = self.config["vessel_types"][v_type]

                # Vessel-Fuel engineering compatibility check
                compat_fuels = VESSEL_FUEL_COMPATIBILITY.get(v_type, ["HFO", "MGO"])
                if fuel_type not in compat_fuels:
                    constraint_violations["vessel_compatibility"] += float(n_vessels) * 10.0

                # Bunkering feasibility check: fuel must be supported at origin or destination
                orig_supp = fuel_type in orig_port.get("supported_fuels", [])
                dest_supp = fuel_type in dest_port.get("supported_fuels", [])
                if not (orig_supp or dest_supp):
                    constraint_violations["fuel_bunkering"] += float(n_vessels)

                # Round trips performed annually by this option
                ann_trips = n_vessels * max_trips_per_vessel
                route_annual_trips += ann_trips

                # Cargo capacity with alternative fuel tank penalty
                nom_teu = float(v_cfg["capacity_teu"])
                usable_teu = calculate_usable_capacity_teu(nom_teu, fuel_type, self.config)
                route_cargo_cap += ann_trips * usable_teu

                # Average cargo load mass (assume 12.0 tonnes per laden TEU)
                avg_cargo_tonnes = min(float(v_cfg["capacity_dwt"]), usable_teu * 12.0 * 0.85)
                route_cargo_tonnes_cap += ann_trips * avg_cargo_tonnes

                # Sea leg fuel (round trip = 2 legs)
                leg_fuel_hfo, _ = calculate_leg_fuel_conventional(
                    vessel_cfg=v_cfg,
                    speed_knots=speed,
                    distance_nm=dist_nm,
                    cargo_load_tonnes=avg_cargo_tonnes,
                    weather_severity=weather,
                    k_w=float(self.config["general"].get("weather_penalty_k_w", 0.35)),
                )
                rt_fuel_hfo = 2.0 * leg_fuel_hfo

                # Convert to actual fuel mass & energy
                actual_fuel_tonnes = calculate_alternative_fuel_mass(rt_fuel_hfo, fuel_type, self.config)
                actual_fuel_gj = calculate_fuel_energy_gj(actual_fuel_tonnes, fuel_type, self.config)

                ann_fuel_tonnes = ann_trips * actual_fuel_tonnes
                ann_fuel_gj = ann_trips * actual_fuel_gj
                total_fuel_gj += ann_fuel_gj
                total_fuel_tonnes_hfo_eq += ann_trips * rt_fuel_hfo

                # Emissions from propulsion
                prop_emissions = calculate_emissions(ann_fuel_tonnes, fuel_type, pathway, self.config)
                total_emissions_co2e += prop_emissions["total_co2e"]
                total_ttw_emissions += prop_emissions["tank_to_wake"]
                total_wtt_emissions += prop_emissions["well_to_tank"]
                total_slip_emissions += prop_emissions.get("slip", 0.0)

                route_ttw_emiss += prop_emissions["tank_to_wake"]
                route_wtt_emiss += prop_emissions["well_to_tank"]
                route_slip_emiss += prop_emissions.get("slip", 0.0)

                # Economic costs
                # 1. Fuel cost
                fuel_price = get_fuel_price_usd_per_tonne(fuel_type, pathway, self.config) * self.fuel_price_multiplier
                ann_fuel_cost = ann_fuel_tonnes * fuel_price

                # 2. Vessel capital / time-charter cost
                daily_charter = float(v_cfg["daily_charter_usd"])
                ann_charter_cost = n_vessels * (daily_charter * self.operating_days_year)

                # 3. Port call fees
                port_fees_rt = float(orig_port["port_call_fee_usd"]) + float(dest_port["port_call_fee_usd"])
                ann_port_fees = ann_trips * port_fees_rt

                # 4. Port berth auxiliary energy & emissions
                aux_kw = float(v_cfg["aux_kw_berth"])
                berth_orig = calculate_berth_energy_and_emissions(
                    aux_kw, float(orig_port["berth_hours_avg"]), shore_power[r_cfg["origin"]], orig_port, self.config
                )
                berth_dest = calculate_berth_energy_and_emissions(
                    aux_kw, float(dest_port["berth_hours_avg"]), shore_power[r_cfg["destination"]], dest_port, self.config
                )

                ann_berth_cost = ann_trips * (berth_orig["cost_usd"] + berth_dest["cost_usd"])
                ann_berth_emissions = ann_trips * (berth_orig["emissions_co2e"] + berth_dest["emissions_co2e"])

                total_emissions_co2e += ann_berth_emissions
                total_berth_emissions += ann_berth_emissions
                route_berth_emiss += ann_berth_emissions

                total_operating_cost += ann_fuel_cost + ann_charter_cost + ann_port_fees + ann_berth_cost

                # Reliability
                rel = calculate_schedule_reliability(speed, float(v_cfg["v_max_knots"]), weather)
                route_reliabilities.append((n_vessels, rel))

            # Cargo actually moved = min(route capacity, annual demand)
            cargo_actually_moved_teu = min(route_cargo_cap, annual_demand)
            total_cargo_delivered_teu += cargo_actually_moved_teu

            # Oversupply ratio: supplied capacity / demand
            oversupply_ratio = route_cargo_cap / max(1e-6, annual_demand)

            # Transport work must use cargo actually moved (tonnes * distance)
            if route_cargo_cap > 0:
                avg_tonnes_per_teu = route_cargo_tonnes_cap / route_cargo_cap
                cargo_actually_moved_tonnes = cargo_actually_moved_teu * avg_tonnes_per_teu
            else:
                cargo_actually_moved_tonnes = 0.0

            route_transport_work = cargo_actually_moved_tonnes * rt_distance
            total_transport_work_tnm += route_transport_work

            # Check route-level constraints
            # 2. Demand constraint
            if route_cargo_cap < annual_demand:
                shortfall_ratio = (annual_demand - route_cargo_cap) / annual_demand
                constraint_violations["demand"] += shortfall_ratio * 10.0

            # 3. Supply cap constraint (if configured)
            if self.supply_cap_ratio is not None and oversupply_ratio > self.supply_cap_ratio:
                excess_ratio = (oversupply_ratio - self.supply_cap_ratio) / self.supply_cap_ratio
                constraint_violations["supply_cap"] += excess_ratio * 10.0

            # 4. Frequency constraint (sailings per week)
            sailings_per_week = route_annual_trips / 52.0
            if sailings_per_week < min_freq:
                freq_shortfall = (min_freq - sailings_per_week) / min_freq
                constraint_violations["frequency"] += freq_shortfall * 5.0

            # 5. Reliability constraint
            if route_reliabilities:
                total_v = sum(r[0] for r in route_reliabilities)
                avg_rel = sum(r[0] * r[1] for r in route_reliabilities) / max(1, total_v)
            else:
                avg_rel = 0.0

            if avg_rel < self.reliability_threshold:
                constraint_violations["reliability"] += (self.reliability_threshold - avg_rel) * 10.0

            route_details[r_key] = {
                "speed_knots": speed,
                "vessels_assigned": route_assigned_vessels,
                "annual_capacity_teu": route_cargo_cap,
                "annual_demand_teu": annual_demand,
                "cargo_moved_teu": cargo_actually_moved_teu,
                "oversupply_ratio": round(oversupply_ratio, 3),
                "sailings_per_week": sailings_per_week,
                "min_sailings_per_week": min_freq,
                "reliability": avg_rel,
                "transport_work_tnm": route_transport_work,
                "voyage_ttw_emissions_t": route_ttw_emiss,
                "voyage_wtt_emissions_t": route_wtt_emiss,
                "berth_emissions_t": route_berth_emiss,
                "slip_emissions_t": route_slip_emiss,
            }

        # Carbon tax addition to operating cost
        carbon_tax_total = total_emissions_co2e * self.carbon_tax_rate
        total_operating_cost += carbon_tax_total

        # 5. Carbon Intensity Proxy (gCO2e per tonne-nm)
        if total_transport_work_tnm > 0:
            carbon_intensity = (total_emissions_co2e * 1e6) / total_transport_work_tnm
        else:
            carbon_intensity = 999.0

        if carbon_intensity > self.carbon_intensity_cap:
            ci_excess = (carbon_intensity - self.carbon_intensity_cap) / self.carbon_intensity_cap
            constraint_violations["carbon_intensity"] += ci_excess * 10.0

        total_violation_score = sum(constraint_violations.values())
        is_feasible = bool(total_violation_score < 1e-4)

        # Normalized weighted-sum composite objective
        obj_fuel = total_fuel_gj / self.norm_fuel_gj
        obj_cost = total_operating_cost / self.norm_cost_usd
        obj_emissions = total_emissions_co2e / self.norm_emissions_t

        base_objective = (
            self.w_fuel * obj_fuel + self.w_cost * obj_cost + self.w_emissions * obj_emissions
        )

        fitness = base_objective + (self.penalty_weight * total_violation_score)

        return {
            "fitness": float(fitness),
            "base_objective": float(base_objective),
            "is_feasible": is_feasible,
            "total_fuel_gj": float(total_fuel_gj),
            "total_fuel_tonnes_hfo_eq": float(total_fuel_tonnes_hfo_eq),
            "total_operating_cost_usd": float(total_operating_cost),
            "total_emissions_co2e_tonnes": float(total_emissions_co2e),
            "carbon_intensity_g_tnm": float(carbon_intensity),
            "total_transport_work_tnm": float(total_transport_work_tnm),
            "total_cargo_delivered_teu": float(total_cargo_delivered_teu),
            "constraint_violations": constraint_violations,
            "total_violation_score": float(total_violation_score),
            "allocations": allocations,
            "speeds": speeds,
            "shore_power": shore_power,
            "route_details": route_details,
            "vessels_used_by_type": vessels_used_by_type,
            "emissions_breakdown": {
                "ttw_co2e_tonnes": float(total_ttw_emissions),
                "wtt_co2e_tonnes": float(total_wtt_emissions),
                "slip_co2e_tonnes": float(total_slip_emissions),
                "berth_co2e_tonnes": float(total_berth_emissions),
                "total_co2e_tonnes": float(total_emissions_co2e),
            },
        }

    def fitness_function(self, bits: np.ndarray) -> float:
        """Scalar fitness for single-objective optimization engines."""
        return self.evaluate(bits)["fitness"]
