"""Synthetic industrial telemetry generator.

ALL VALUES ARE SYNTHETIC MODEL DATA. They are not Colonial Pipeline telemetry and not measurements of any
real system. Normal ranges, units and anomaly magnitudes are documented assumptions (docs/telemetry_assumptions.md).

Each row = one component at one 1-minute step: timestamp, component id, zone, feature values, ground-truth
label and severity. Anomalies are injected from a simulated attack/failure trace so detection is evaluated
against known ground truth. Training, validation and test data come from DIFFERENT episodes (different seeds),
never from random rows of one episode.
"""
from __future__ import annotations

import zlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ..config import settings
from ..infrastructure.enums import NodeType as NT, Zone
from ..infrastructure.graph_builder import InfrastructureGraph
from ..infrastructure.telemetry_spec import TELEMETRY_FEATURES

FEATURES = list(TELEMETRY_FEATURES.keys())
FLOW_NOMINAL = {"PH01": 900, "PH02": 900, "PH03": 900, "PH04": 900, "PH05": 900, "PH06": 400, "PH07": 900, "PH08": 900}
PRESSURE_NOMINAL = {"PH01": 60, "PH02": 57, "PH03": 56, "PH04": 62, "PH05": 58, "PH07": 50}
# physics-consistency (mass-balance) residual: node flow minus its upstream reference sensor
RESIDUAL_REF = {"PH02": "PH01", "PH03": "PH02", "PH04": "PH03", "PH05": "PH04", "PH08": "PH07"}
START = datetime(2026, 1, 1, 0, 0, 0)

LABEL_NORMAL = "normal"
SEVERITY = {"normal": 0, "cyber_activity": 2, "downstream_effect": 2, "ransomware": 3, "physical_failure": 3}


def _u(node_id: str, feat: str) -> float:
    return 0.3 + 0.4 * (zlib.crc32(f"{node_id}:{feat}".encode()) % 1000) / 1000.0


def _series(rng, mu, sd, n, phi=0.5):
    eps = rng.normal(0, sd * np.sqrt(1 - phi * phi), n)
    x = np.empty(n)
    x[0] = mu + rng.normal(0, sd)
    for t in range(1, n):
        x[t] = mu + phi * (x[t - 1] - mu) + eps[t]
    return x


def detection_features(node) -> list:
    f = list(node.telemetry_features)
    if node.id in RESIDUAL_REF:
        f.append("flow_residual_m3h")
    return f


def _base(node, feat, rng, n):
    spec = TELEMETRY_FEATURES[feat]
    rng_width = spec.normal_high - spec.normal_low
    if feat == "pump_state":
        return _series(rng, 1.0, 0.015, n)
    if feat == "valve_position_pct":
        return np.clip(_series(rng, 97.0, 1.2, n), 0, 100)
    if feat == "pressure_bar":
        return _series(rng, PRESSURE_NOMINAL.get(node.id, 55), 1.5, n)
    if feat == "flow_m3h":
        return _series(rng, FLOW_NOMINAL.get(node.id, 900), 12.0, n)
    if feat == "temperature_c":
        return _series(rng, 25.0, 1.2, n)
    if feat == "tank_level_pct":
        return np.clip(_series(rng, 60.0, 1.5, n, phi=0.97), 0, 100)
    mu = spec.normal_low + rng_width * _u(node.id, feat)
    return np.clip(_series(rng, mu, rng_width / 12.0, n), 0, None)


def _descendants(ig, nid):
    fg = ig.flow_graph()
    import networkx as nx
    return set(nx.descendants(fg, nid)) if nid in fg else set()


def generate_episode(ig: InfrastructureGraph, seed: int, trace: dict = None, episode_id: str = "ep",
                     scenario_id: str = "normal", n_steps: int = settings.EPISODE_STEPS,
                     onset: int = settings.ATTACK_ONSET_STEP, per_hop: int = settings.STEPS_PER_HOP) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    S = {n.id: {f: _base(n, f, rng, n_steps) for f in n.telemetry_features} for n in ig.nodes}
    L = {n.id: np.array([LABEL_NORMAL] * n_steps, dtype=object) for n in ig.nodes}

    def rngw(feat):
        sp = TELEMETRY_FEATURES[feat]
        return sp.normal_high - sp.normal_low

    def step_of(t):
        return int(min(n_steps - 1, onset + round(per_hop * t)))

    def label(nid, a, b, lab):
        cur = L[nid][a:b]
        # keep the most severe label already present
        for i in range(len(cur)):
            if SEVERITY[lab] >= SEVERITY[cur[i]]:
                cur[i] = lab
        L[nid][a:b] = cur

    def addv(nid, feat, a, b, delta):
        if feat in S[nid]:
            S[nid][feat][a:b] = S[nid][feat][a:b] + delta

    def mul(nid, feat, a, b, k):
        if feat in S[nid]:
            S[nid][feat][a:b] = S[nid][feat][a:b] * k

    def setv(nid, feat, a, b, v):
        if feat in S[nid]:
            S[nid][feat][a:b] = v

    if trace:
        comp, failed = trace.get("compromised", {}), trace.get("failed", {})
        services = trace.get("services", {})
        # 1. cyber activity from compromise until failure/end
        for nid, t in comp.items():
            if ig.node(nid).zone == Zone.PHYSICAL:
                continue
            a = step_of(t)
            b = min(n_steps, a + 40)
            for feat, k in (("auth_events_per_min", 2.5), ("conn_per_min", 1.2), ("net_traffic_mbps", 1.5),
                            ("cpu_util_pct", 0.5), ("mem_util_pct", 0.25)):
                if feat in S[nid]:
                    addv(nid, feat, a, b, k * rngw(feat) * (0.8 + 0.4 * rng.random()))
            label(nid, a, b, "cyber_activity")
        # 2. failures
        for nid, (t, kind) in failed.items():
            node, a = ig.node(nid), step_of(t)
            if kind == "ransomware":
                b = min(n_steps, a + 10)
                setv(nid, "cpu_util_pct", a, b, 95.0 + rng.normal(0, 2, b - a))
                addv(nid, "net_traffic_mbps", a, b, 2.5 * rngw("net_traffic_mbps"))
                setv(nid, "cpu_util_pct", b, n_steps, 1.5)
                setv(nid, "net_traffic_mbps", b, n_steps, 0.2)
                setv(nid, "mem_util_pct", b, n_steps, 5.0)
                setv(nid, "auth_events_per_min", b, n_steps, 0.0)
                setv(nid, "conn_per_min", b, n_steps, 0.0)
                label(nid, a, n_steps, "ransomware")
            elif node.zone == Zone.PHYSICAL:
                desc = _descendants(ig, nid)
                if node.node_type == NT.PUMP_STATION:
                    setv(nid, "pump_state", a, n_steps, 0.02)
                    mul(nid, "pressure_bar", a, n_steps, 0.3)
                    mul(nid, "flow_m3h", a, n_steps, 0.04)
                    starve = True
                elif node.node_type == NT.PIPELINE_SEGMENT:
                    mul(nid, "pressure_bar", a, n_steps, 0.15)
                    mul(nid, "flow_m3h", a, n_steps, 0.30)      # inlet sensor still reads flow -> imbalance
                    starve = True
                elif node.node_type == NT.BLOCK_VALVE:
                    setv(nid, "valve_position_pct", a, n_steps, 2.0)
                    mul(nid, "flow_m3h", a, n_steps, 0.04)
                    starve = True
                    for p in ig.g.predecessors(nid):
                        if p in S and ig.node(p).zone == Zone.PHYSICAL:
                            mul(p, "pressure_bar", a, n_steps, 1.35)
                            label(p, a, n_steps, "downstream_effect")
                elif node.node_type == NT.STORAGE_TANK:
                    k = min(30, n_steps - a)
                    S[nid]["tank_level_pct"][a:a + k] = np.linspace(S[nid]["tank_level_pct"][a], 5.0, k)
                    S[nid]["tank_level_pct"][a + k:] = 5.0
                    mul(nid, "flow_m3h", a, n_steps, 0.10)
                    starve = False
                else:
                    mul(nid, "flow_m3h", a, n_steps, 0.05)
                    starve = True
                label(nid, a, n_steps, "physical_failure")
                if starve:
                    for d in desc:
                        if d in S and d != nid:
                            mul(d, "flow_m3h", a, n_steps, 0.05)
                            mul(d, "pressure_bar", a, n_steps, 0.3)
                            label(d, a, n_steps, "downstream_effect")
        # 3. dependency-degraded physical assets (e.g. billing dependency) reduce deliveries
        if failed and services:
            a0 = step_of(min(t for t, _ in failed.values()))
            for n in ig.nodes:
                sv = services.get(n.id, 1.0)
                if n.zone == Zone.PHYSICAL and n.id not in failed and 0.3 <= sv < 0.95:
                    mul(n.id, "flow_m3h", a0, n_steps, sv)
                    label(n.id, a0, n_steps, "downstream_effect")

    # derived mass-balance residual
    for nid, ref in RESIDUAL_REF.items():
        if "flow_m3h" in S[nid] and "flow_m3h" in S[ref]:
            S[nid]["flow_residual_m3h"] = S[nid]["flow_m3h"] - S[ref]["flow_m3h"]

    frames = []
    ts = [(START + timedelta(minutes=i)).isoformat() for i in range(n_steps)]
    for n in ig.nodes:
        d = {"episode_id": episode_id, "scenario_id": scenario_id, "step": np.arange(n_steps), "timestamp": ts,
             "component_id": n.id, "zone": n.zone.value}
        for f in FEATURES:
            d[f] = S[n.id].get(f, np.full(n_steps, np.nan))
        d["label"] = L[n.id]
        d["severity"] = [SEVERITY[x] for x in L[n.id]]
        frames.append(pd.DataFrame(d))
    return pd.concat(frames, ignore_index=True)
