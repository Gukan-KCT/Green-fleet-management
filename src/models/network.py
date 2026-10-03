"""
Network Definition & Plumbing for Custom Ports and Corridors.

Provides schema validation, Great-Circle (Haversine) distance calculation with
configurable shipping-lane detour factors, JSON serialization/deserialization,
and bridge constructors for FleetOptimizationProblem.
"""

from __future__ import annotations
import math
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

import yaml
from pathlib import Path

from src.models.physics import load_config
from src.optimization.problem import FleetOptimizationProblem, DEFAULT_CANDIDATE_OPTIONS


EARTH_RADIUS_NM = 3440.065  # Nautical miles (6371 km / 1.852 km/nm)


def calculate_haversine_distance_nm(
    lat1: float, lon1: float, lat2: float, lon2: float, detour_factor: float = 1.15
) -> float:
    """
    Computes approximate nautical miles between two coordinates using Haversine formula
    multiplied by a shipping lane detour factor.

    Disclaimer: Great-circle distance with synthetic detour factor.
    Not for actual sea navigation.
    """
    # Convert latitude and longitude from degrees to radians
    phi1, lambda1 = math.radians(lat1), math.radians(lon1)
    phi2, lambda2 = math.radians(lat2), math.radians(lon2)

    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    great_circle = EARTH_RADIUS_NM * c
    return round(great_circle * detour_factor, 1)


@dataclass
class PortDefinition:
    id: str
    name: str
    lat: float
    lon: float
    country: str = "Custom"
    has_shore_power: bool = False
    supported_fuels: List[str] = field(default_factory=lambda: ["HFO", "MGO"])
    grid_ef_tonnes_per_mwh: float = 0.65
    electricity_price_usd_per_mwh: float = 125.0
    port_call_fee_usd: float = 6500.0
    berth_hours_avg: float = 24.0
    coordinates_note: str = "approximate, verify"

    def validate(self) -> List[str]:
        errors = []
        if not self.name or not self.id:
            errors.append("Port name and ID cannot be empty.")
        if not (-90.0 <= self.lat <= 90.0):
            errors.append(f"Invalid latitude {self.lat}. Must be between -90 and 90.")
        if not (-180.0 <= self.lon <= 180.0):
            errors.append(f"Invalid longitude {self.lon}. Must be between -180 and 180.")
        if not self.supported_fuels:
            errors.append("Port must support at least one bunkering fuel.")
        return errors


@dataclass
class RouteDefinition:
    id: str
    name: str
    origin: str
    destination: str
    annual_demand_teu: int
    distance_nm: float
    sea_conditions: str = "Moderate"  # Calm, Moderate, Rough
    weather_severity: float = 0.30
    min_sailings_per_week: float = 1.0
    speed_cap_knots: float = 18.0
    is_distance_overridden: bool = False

    def validate(self, valid_port_ids: set[str]) -> List[str]:
        errors = []
        if self.origin == self.destination:
            errors.append(f"Route {self.id}: Origin and Destination cannot be the same port ({self.origin}).")
        if self.origin not in valid_port_ids:
            errors.append(f"Route {self.id}: Origin port '{self.origin}' not found in network ports.")
        if self.destination not in valid_port_ids:
            errors.append(f"Route {self.id}: Destination port '{self.destination}' not found in network ports.")
        if self.annual_demand_teu <= 0:
            errors.append(f"Route {self.id}: Annual demand must be greater than 0 TEU.")
        if self.distance_nm <= 0:
            errors.append(f"Route {self.id}: Distance must be greater than 0 nm.")
        return errors


@dataclass
class Network:
    name: str = "Demo Network"
    is_demo: bool = True
    ports: Dict[str, PortDefinition] = field(default_factory=dict)
    routes: Dict[str, RouteDefinition] = field(default_factory=dict)

    def compute_hash(self) -> str:
        """Computes deterministic MD5 hash of network topology for cache isolation."""
        payload = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_demo": self.is_demo,
            "disclaimer": "Custom network, synthetic parameters. Approximate distances, verify with nautical charts.",
            "ports": {pid: asdict(p) for pid, p in self.ports.items()},
            "routes": {rid: asdict(r) for rid, r in self.routes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Tuple[Optional[Network], List[str]]:
        errors = []
        if not isinstance(data, dict):
            return None, ["Invalid network data format (expected JSON object)."]

        name = str(data.get("name", "Imported Network"))
        is_demo = bool(data.get("is_demo", False))

        raw_ports = data.get("ports", {})
        if not raw_ports:
            errors.append("Network contains no ports.")

        ports = {}
        for pid, pdata in raw_ports.items():
            try:
                pdef = PortDefinition(
                    id=str(pid),
                    name=pdata.get("name", pid.title()),
                    lat=float(pdata.get("lat", 0.0)),
                    lon=float(pdata.get("lon", 0.0)),
                    country=pdata.get("country", "Custom"),
                    has_shore_power=bool(pdata.get("has_shore_power", False)),
                    supported_fuels=list(pdata.get("supported_fuels", ["HFO", "MGO"])),
                    grid_ef_tonnes_per_mwh=float(pdata.get("grid_ef_tonnes_per_mwh", 0.65)),
                    electricity_price_usd_per_mwh=float(pdata.get("electricity_price_usd_per_mwh", 125.0)),
                    port_call_fee_usd=float(pdata.get("port_call_fee_usd", 6500.0)),
                    berth_hours_avg=float(pdata.get("berth_hours_avg", 24.0)),
                    coordinates_note=str(pdata.get("coordinates_note", "approximate, verify")),
                )
                p_errs = pdef.validate()
                if p_errs:
                    errors.extend(p_errs)
                else:
                    ports[pid] = pdef
            except Exception as e:
                errors.append(f"Error parsing port '{pid}': {str(e)}")

        raw_routes = data.get("routes", {})
        if not raw_routes:
            errors.append("Network contains no routes.")

        routes = {}
        port_ids = set(ports.keys())
        for rid, rdata in raw_routes.items():
            try:
                rdef = RouteDefinition(
                    id=str(rid),
                    name=rdata.get("name", rid),
                    origin=str(rdata.get("origin", "")),
                    destination=str(rdata.get("destination", "")),
                    annual_demand_teu=int(rdata.get("annual_demand_teu", 0)),
                    distance_nm=float(rdata.get("distance_nm", 0.0)),
                    sea_conditions=str(rdata.get("sea_conditions", "Moderate")),
                    weather_severity=float(rdata.get("weather_severity", 0.30)),
                    min_sailings_per_week=float(rdata.get("min_sailings_per_week", 1.0)),
                    speed_cap_knots=float(rdata.get("speed_cap_knots", 18.0)),
                    is_distance_overridden=bool(rdata.get("is_distance_overridden", False)),
                )
                r_errs = rdef.validate(port_ids)
                if r_errs:
                    errors.extend(r_errs)
                else:
                    routes[rid] = rdef
            except Exception as e:
                errors.append(f"Error parsing route '{rid}': {str(e)}")

        if errors:
            return None, errors

        net = cls(name=name, is_demo=is_demo, ports=ports, routes=routes)
        return net, []


def get_demo_network() -> Network:
    """Constructs the default demo network directly from system params.yaml."""
    cfg = load_config()
    ports = {}
    for pid, pdata in cfg.get("ports", {}).items():
        ports[pid] = PortDefinition(
            id=pid,
            name=pdata.get("name", pid.title()),
            lat=float(pdata.get("lat", 0.0)),
            lon=float(pdata.get("lon", 0.0)),
            country=pdata.get("country", "India"),
            has_shore_power=bool(pdata.get("has_shore_power", False)),
            supported_fuels=list(pdata.get("supported_fuels", ["HFO", "MGO"])),
            grid_ef_tonnes_per_mwh=float(pdata.get("grid_ef_tonnes_per_mwh", 0.65)),
            electricity_price_usd_per_mwh=float(pdata.get("electricity_price_usd_per_mwh", 125.0)),
            port_call_fee_usd=float(pdata.get("port_call_fee_usd", 6500.0)),
            berth_hours_avg=float(pdata.get("berth_hours_avg", 24.0)),
            coordinates_note=pdata.get("coordinates_note", "approximate, verify"),
        )

    routes = {}
    for rid, rdata in cfg.get("routes", {}).items():
        routes[rid] = RouteDefinition(
            id=rid,
            name=rdata.get("name", rid),
            origin=rdata.get("origin", ""),
            destination=rdata.get("destination", ""),
            annual_demand_teu=int(rdata.get("annual_demand_teu", 100000)),
            distance_nm=float(rdata.get("distance_nm", 500.0)),
            sea_conditions="Moderate",
            weather_severity=float(rdata.get("weather_severity", 0.30)),
            min_sailings_per_week=float(rdata.get("min_sailings_per_week", 1.0)),
            speed_cap_knots=float(rdata.get("speed_cap_knots", 18.0)),
        )

    return Network(name="South Asia Feeder Baseline", is_demo=True, ports=ports, routes=routes)


def load_ports_catalog() -> Dict[str, Dict[str, Any]]:
    """Loads ports from config/ports_catalog.yaml if available, falling back to params.yaml."""
    catalog_path = Path(__file__).resolve().parents[2] / "config" / "ports_catalog.yaml"
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    cfg = load_config()
    return cfg.get("ports", {})


def build_problem_from_network(
    network: Network,
    weights: Optional[Dict[str, float] | Tuple[float, float, float]] = None,
    candidate_options: Optional[List[Dict[str, str]]] = None,
    speed_cap: float = 18.0,
    shore_power_forced: Optional[bool] = None,
) -> FleetOptimizationProblem:
    """
    Constructs a FleetOptimizationProblem instance backed by custom ports and routes
    from a Network instance while strictly reusing the existing physics and fuel availability rules.
    """
    base_cfg = load_config()

    # Build ports dict for config injection
    ports_dict = {}
    for pid, p in network.ports.items():
        ports_dict[pid] = {
            "name": p.name,
            "country": p.country,
            "lat": p.lat,
            "lon": p.lon,
            "coordinates_note": p.coordinates_note,
            "has_shore_power": p.has_shore_power,
            "grid_ef_tonnes_per_mwh": p.grid_ef_tonnes_per_mwh,
            "electricity_price_usd_per_mwh": p.electricity_price_usd_per_mwh,
            "port_call_fee_usd": p.port_call_fee_usd,
            "berth_hours_avg": p.berth_hours_avg,
            "supported_fuels": p.supported_fuels,
        }

    # Build routes dict
    routes_dict = {}
    for rid, r in network.routes.items():
        routes_dict[rid] = {
            "id": r.id,
            "name": r.name,
            "origin": r.origin,
            "destination": r.destination,
            "distance_nm": r.distance_nm,
            "annual_demand_teu": r.annual_demand_teu,
            "min_sailings_per_week": r.min_sailings_per_week,
            "weather_severity": r.weather_severity,
            "speed_cap_knots": min(speed_cap, r.speed_cap_knots),
        }

    # Clone configuration with custom network topology
    custom_cfg = dict(base_cfg)
    custom_cfg["ports"] = ports_dict
    custom_cfg["routes"] = routes_dict

    w_dict = None
    if isinstance(weights, tuple) and len(weights) == 3:
        w_dict = {"fuel": float(weights[0]), "cost": float(weights[1]), "emissions": float(weights[2])}
    elif isinstance(weights, dict):
        w_dict = weights

    return FleetOptimizationProblem(
        config=custom_cfg,
        candidate_options=candidate_options or DEFAULT_CANDIDATE_OPTIONS,
        weights=w_dict,
        routes_override=routes_dict,
        speed_cap_delta=speed_cap - 18.0,
        shore_power_forced=shore_power_forced,
    )


def explain_infeasibility(problem: FleetOptimizationProblem, eval_res: Dict[str, Any]) -> List[str]:
    """
    Analyzes constraint violations and generates computed, actionable diagnostic suggestions.
    """
    suggestions = []
    violations = eval_res.get("constraint_violations", {})
    route_details = eval_res.get("route_details", {})

    # 1. Cargo demand shortfall
    if violations.get("cargo_demand", 0.0) > 0.0:
        for r_k, r_det in route_details.items():
            demand = r_det.get("annual_demand_teu", 0)
            cap = r_det.get("route_cargo_cap", 0)
            if cap < demand:
                shortfall = demand - cap
                max_vsl_cap = 4200 * 50  # approx max annual capacity of 1 Panamax
                ratio = demand / max(1, cap)
                suggestions.append(
                    f"Route {r_k} ({r_det.get('origin', '')} → {r_det.get('destination', '')}) has a demand deficit of "
                    f"{shortfall:,.0f} TEU/yr (delivered {cap:,.0f} vs demand {demand:,.0f}, need {ratio:.1f}x capacity). "
                    f"Suggestion: Reduce annual TEU demand or allow larger feeder vessel types."
                )

    # 2. Service frequency
    if violations.get("service_frequency", 0.0) > 0.0:
        for r_k, r_det in route_details.items():
            sailings = r_det.get("sailings_per_week", 0.0)
            min_req = float(problem.routes[r_k].get("min_sailings_per_week", 1.0))
            if sailings < min_req:
                suggestions.append(
                    f"Route {r_k} provides {sailings:.2f} sailings/wk vs minimum required {min_req:.2f} sailings/wk. "
                    f"Suggestion: Increase deployed vessels on this route or increase cruising speed."
                )

    # 3. Schedule reliability
    if violations.get("schedule_reliability", 0.0) > 0.0:
        for r_k, r_det in route_details.items():
            rel = r_det.get("reliability", 1.0)
            if rel < problem.reliability_threshold:
                suggestions.append(
                    f"Route {r_k} schedule reliability is {rel*100:.1f}% (below threshold {problem.reliability_threshold*100:.0f}%). "
                    f"Suggestion: Reduce route speed, lower weather severity, or deploy faster vessels with higher sea margins."
                )

    # 4. Fuel bunkering compatibility
    if violations.get("fuel_bunkering", 0.0) > 0.0:
        for r_k, r_det in route_details.items():
            orig_id = problem.routes[r_k]["origin"]
            dest_id = problem.routes[r_k]["destination"]
            orig_p = problem.config["ports"].get(orig_id, {})
            dest_p = problem.config["ports"].get(dest_id, {})
            orig_fuels = orig_p.get("supported_fuels", [])
            dest_fuels = dest_p.get("supported_fuels", [])
            suggestions.append(
                f"Fuel availability failure on corridor {orig_p.get('name', orig_id)} → {dest_p.get('name', dest_id)}. "
                f"Origin supports {orig_fuels}; Destination supports {dest_fuels}. "
                f"Suggestion: Enable matching alternative bunker fuels at origin or destination port."
            )

    # 5. Fleet availability
    if violations.get("fleet_availability", 0.0) > 0.0:
        suggestions.append(
            "Fleet availability limit exceeded: Total vessels assigned across routes exceed the operator available fleet. "
            "Suggestion: Rebalance vessel allocations across routes."
        )

    if not suggestions:
        suggestions.append(
            "Optimization penalty triggered. Review route distance, vessel speed limits, and bunkering compatibility."
        )

    return suggestions
