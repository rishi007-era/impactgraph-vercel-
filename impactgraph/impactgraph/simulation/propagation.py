"""Deterministic consequence model: dependency-based service loss and product-flow throughput.

Given a set of failed components (and optionally severed dependencies / closed valves), compute

  service level s_i in [0,1] for every component, using the dependency graph in topological order:
      s_i = 0                                         if i failed
      s_i = prod_over_dependencies (1 - w_e * (1 - s_src(e)))      otherwise
  where w_e is the edge's dependency_strength. A dependency whose underlying link was isolated
  counts as having a failed source (s_src = 0) for that edge.

  delivered throughput = max-flow from the pump-station source to the delivery point, where every
  physical component's capacity is capacity_m3h * s_i (node splitting), and closed valves carry 0.

  release hazard = flow that could still enter a ruptured/leaking asset, relative to baseline throughput.

Assumptions: service loss multiplies across dependencies (independent), thresholds below are
documented model choices, and flow is steady-state (no transient hydraulics).
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from ..config import settings
from ..infrastructure.enums import Condition, EdgeType, NodeType, Zone
from ..infrastructure.graph_builder import InfrastructureGraph

FAILED_BELOW = 0.30      # service level below this is classed FAILED
DEGRADED_BELOW = 0.95    # service level below this is classed DEGRADED
SOURCE_NODE = "PH01"
SINK_NODE = "PH08"


@dataclass
class Consequence:
    services: dict
    throughput_fraction: float
    service_loss: float          # importance-weighted mean service loss over all components
    hazard: float                # 0..1 release exposure
    impact: float                # operational part of residual impact (exposure term is added per trial)


class PropagationModel:
    def __init__(self, ig: InfrastructureGraph):
        self.ig = ig
        self.ids = [n.id for n in ig.nodes]
        self.importance = {n.id: n.operational_importance for n in ig.nodes}
        self.total_importance = sum(self.importance.values())
        dep = nx.DiGraph()
        dep.add_nodes_from(self.ids)
        self.dep_in = {i: [] for i in self.ids}
        for e in ig.edges_by_type(EdgeType.SERVICE_DEP, EdgeType.OPERATIONAL_DEP):
            dep.add_edge(e.source, e.target)
            self.dep_in[e.target].append(e)
        self.topo = list(nx.topological_sort(dep))
        self.flow_edges = ig.edges_by_type(EdgeType.PHYSICAL_FLOW)
        self.phys = [n for n in ig.nodes if n.zone == Zone.PHYSICAL]
        self.phys_ids = [n.id for n in self.phys]
        self.baseline_throughput = self._max_flow({i: 1.0 for i in self.ids}, frozenset())
        self.attack_pairs = {}
        for e in ig.edges:
            if e.is_attack_traversable:
                self.attack_pairs.setdefault((e.source, e.target), []).append(e.id)
        self._cache: dict = {}

    # ---- helpers -----------------------------------------------------
    def severed_dependencies(self, isolated_edges) -> frozenset:
        """Dependency edges whose underlying communication link was isolated (same endpoints)."""
        sev = set()
        for eid in isolated_edges:
            e = self.ig.edge(eid)
            if not e.is_attack_traversable:
                continue
            for d in self.dep_in[e.target]:
                if d.source == e.source:
                    sev.add(d.id)
        return frozenset(sev)

    def closed_flow_edges(self, isolated_edges) -> frozenset:
        return frozenset(eid for eid in isolated_edges if self.ig.edge(eid).edge_type == EdgeType.PHYSICAL_FLOW)

    def compute_services(self, failed, severed) -> dict:
        s = {}
        for i in self.topo:
            if i in failed:
                s[i] = 0.0
                continue
            v = 1.0
            for d in self.dep_in[i]:
                src = 0.0 if d.id in severed else s[d.source]
                v *= 1.0 - d.dependency_strength * (1.0 - src)
            s[i] = v
        return s

    def _flow_graph(self, services, closed, extra_sink=None, free_node=None):
        G = nx.DiGraph()
        for n in self.phys:
            sv = 1.0 if n.id == free_node else services[n.id]
            G.add_edge(n.id + "_in", n.id + "_out", capacity=n.capacity_m3h * sv)
        for e in self.flow_edges:
            cap = 0.0 if e.id in closed else e.flow_capacity_m3h
            u, v = e.source + "_out", e.target + "_in"
            if G.has_edge(u, v):
                G[u][v]["capacity"] += cap
            else:
                G.add_edge(u, v, capacity=cap)
        G.add_edge("S", SOURCE_NODE + "_in", capacity=1e9)
        G.add_edge(SINK_NODE + "_out", "T", capacity=1e9)
        return G

    def _max_flow(self, services, closed, free_node=None, sink="T") -> float:
        G = self._flow_graph(services, closed, free_node=free_node)
        return nx.maximum_flow_value(G, "S", sink)

    def conditions(self, services, compromised) -> dict:
        out = {}
        for i in self.ids:
            sv = services[i]
            if sv < FAILED_BELOW:
                out[i] = Condition.FAILED
            elif i in compromised:
                out[i] = Condition.COMPROMISED
            elif sv < DEGRADED_BELOW:
                out[i] = Condition.DEGRADED
            else:
                out[i] = Condition.NORMAL
        return out

    # ---- main entry --------------------------------------------------
    def evaluate(self, failed, severed=frozenset(), closed=frozenset(), release=frozenset()) -> Consequence:
        key = (frozenset(failed), severed, closed, frozenset(release))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        services = self.compute_services(failed, severed)
        base = self.baseline_throughput
        thr = self._max_flow(services, closed) / base if base > 0 else 0.0
        loss = sum(self.importance[i] * (1.0 - services[i]) for i in self.ids) / self.total_importance
        hazard = 0.0
        for r in release:
            if r in failed:
                inflow = self._max_flow(services, closed, free_node=r, sink=r + "_in")
                hazard = max(hazard, min(1.0, inflow / base))
        w = settings.IMPACT_WEIGHTS
        impact = w["throughput"] * (1.0 - thr) + w["service"] * loss + w["hazard"] * hazard   # exposure added per trial
        res = Consequence(services, thr, loss, hazard, impact)
        self._cache[key] = res
        return res

    def blast_radius_weighted(self, affected) -> float:
        """Importance-weighted share of all components that are compromised, failed or degraded."""
        return sum(self.importance[i] for i in affected) / self.total_importance

    def continuity_without_attack(self, isolated_edges) -> float:
        """Throughput fraction when only the LOGICAL isolations (no attack) are applied.
        Valve closures are reactive (applied only after a release), so they do not count here."""
        sev = self.severed_dependencies(isolated_edges)
        return self.evaluate(frozenset(), sev, frozenset()).throughput_fraction
