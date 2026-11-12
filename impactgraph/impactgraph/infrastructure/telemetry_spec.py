"""Catalogue of synthetic telemetry features.

All ranges are ASSUMED model values for simulation. They are not measurements from
any real pipeline operator. Per-node overrides are applied by the telemetry
generator (Milestone 2); these are the defaults.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryFeature:
    name: str
    unit: str
    normal_low: float
    normal_high: float
    description: str


_FEATURES = [
    TelemetryFeature("cpu_util_pct", "%", 5.0, 55.0, "CPU utilisation"),
    TelemetryFeature("mem_util_pct", "%", 20.0, 70.0, "Memory utilisation"),
    TelemetryFeature("net_traffic_mbps", "Mbit/s", 1.0, 80.0, "Network traffic volume"),
    TelemetryFeature("auth_events_per_min", "events/min", 0.0, 12.0, "Authentication attempts"),
    TelemetryFeature("conn_per_min", "connections/min", 1.0, 60.0, "New connections"),
    TelemetryFeature("pump_state", "run signal (0=stopped,1=running)", 0.95, 1.05, "Pump operating state (normalised run signal with sensor noise)"),
    TelemetryFeature("valve_position_pct", "% open", 60.0, 100.0, "Valve opening"),
    TelemetryFeature("pressure_bar", "bar", 40.0, 70.0, "Line pressure"),
    TelemetryFeature("flow_m3h", "m3/h (model units)", 700.0, 1000.0, "Product flow rate"),
    TelemetryFeature("temperature_c", "deg C", 5.0, 45.0, "Product temperature"),
    TelemetryFeature("tank_level_pct", "% full", 30.0, 85.0, "Storage tank level"),
    TelemetryFeature("flow_residual_m3h", "m3/h (model units)", -40.0, 40.0,
                     "Mass-balance residual: node flow minus upstream sensor flow (derived)"),
]

TELEMETRY_FEATURES = {f.name: f for f in _FEATURES}
