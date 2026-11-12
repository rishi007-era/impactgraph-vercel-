"""Structural and semantic validation of an InfrastructureGraph."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

from .enums import EdgeType, IsolationKind, NodeType, Zone
from .graph_builder import InfrastructureGraph
from .nodes import CONTROLLED_TYPES, TYPE_RULES

ERROR = "error"
WARNING = "warning"


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    subject: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code} {self.subject}: {self.message}"


@dataclass
class ValidationReport:
    issues: list = field(default_factory=list)

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set:
        return {i.code for i in self.issues}

    def add(self, severity: str, code: str, message: str, subject: str = "") -> None:
        self.issues.append(Issue(severity, code, message, subject))

    def summary(self) -> str:
        return f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"


def _cross_zone_allowed(src, dst, edge) -> bool:
    """Security-boundary rules for attack-traversable edges (documented in docs/graph_schema.md)."""
    sz, dz = src.zone, dst.zone
    if sz == dz:
        return True
    if sz == Zone.PHYSICAL:
        return False                       # physical assets never initiate cyber links
    if dz == Zone.PHYSICAL:
        return sz == Zone.OT and edge.edge_type == EdgeType.CONTROL
    gateway_dst = dst.node_type == NodeType.BOUNDARY_GATEWAY
    gateway_src = src.node_type == NodeType.BOUNDARY_GATEWAY
    if sz == Zone.VENDOR and dz == Zone.IT:
        return True
    if sz == Zone.VENDOR and dz == Zone.OT:
        return gateway_dst                 # external access reaches OT only through the DMZ gateway
    if sz == Zone.IT and dz == Zone.OT:
        return gateway_dst
    if sz == Zone.IT and dz == Zone.VENDOR:
        return True                        # outbound
    if sz == Zone.OT and dz == Zone.IT:
        return gateway_src
    return False                           # OT -> vendor and anything else


def validate_graph(ig: InfrastructureGraph, expected_zone_counts: Optional[dict] = None) -> ValidationReport:
    r = ValidationReport()

    # --- duplicate identifiers
    for nid, c in Counter(n.id for n in ig.nodes).items():
        if c > 1:
            r.add(ERROR, "DUP_NODE_ID", f"node id used {c} times", nid)
    for eid, c in Counter(e.id for e in ig.edges).items():
        if c > 1:
            r.add(ERROR, "DUP_EDGE_ID", f"edge id used {c} times", eid)

    # --- node-level checks
    for n in ig.nodes:
        for p in n.validate():
            r.add(ERROR, "NODE_FIELD", p, n.id)
        allowed = TYPE_RULES[n.node_type][1]
        if n.zone not in allowed:
            r.add(ERROR, "NODE_TYPE_ZONE", f"{n.node_type.value} not allowed in zone {n.zone.value}", n.id)

    # --- edge-level checks
    known = {n.id for n in ig.nodes}
    for e in ig.edges:
        for p in e.validate():
            r.add(ERROR, "EDGE_FIELD", p, e.id)
        missing = [x for x in (e.source, e.target) if x not in known]
        if missing:
            r.add(ERROR, "INVALID_REFERENCE", f"unknown endpoint(s) {missing}", e.id)
            continue
        if e.source == e.target:
            r.add(ERROR, "SELF_LOOP", "edge connects a node to itself", e.id)
            continue
        s, t = ig.node(e.source), ig.node(e.target)

        # endpoint rules per relationship type
        if e.edge_type == EdgeType.PHYSICAL_FLOW and not (s.zone == Zone.PHYSICAL and t.zone == Zone.PHYSICAL):
            r.add(ERROR, "EDGE_TYPE_ENDPOINTS", "physical_flow must join two physical assets", e.id)
        if e.edge_type == EdgeType.NETWORK and Zone.PHYSICAL in (s.zone, t.zone):
            r.add(ERROR, "EDGE_TYPE_ENDPOINTS", "network edges cannot touch physical assets (use control)", e.id)
        if e.edge_type == EdgeType.AUTH and Zone.PHYSICAL in (s.zone, t.zone):
            r.add(ERROR, "EDGE_TYPE_ENDPOINTS", "auth edges cannot touch physical assets", e.id)
        if e.edge_type == EdgeType.CONTROL and not (s.zone == Zone.OT and t.zone in (Zone.OT, Zone.PHYSICAL)):
            r.add(ERROR, "EDGE_TYPE_ENDPOINTS", "control edges must start in OT and end in OT or physical", e.id)

        # unrealistic cross-zone connections (attack-traversable only)
        if e.is_attack_traversable and not _cross_zone_allowed(s, t, e):
            r.add(ERROR, "UNREALISTIC_CROSS_ZONE",
                  f"{s.zone.value}->{t.zone.value} {e.edge_type.value} edge bypasses security boundary rules", e.id)

        # logical isolation of a link into a safety-critical component needs explicit review
        if e.isolatable and e.isolation_kind == IsolationKind.LOGICAL and t.safety_critical:
            r.add(WARNING, "SAFETY_REVIEW", "logical isolation targets a safety-critical component", e.id)

    # --- global structure (on the graph built from valid references)
    g = ig.g
    if g.number_of_nodes() > 0:
        comps = list(nx.weakly_connected_components(g))
        if len(comps) > 1:
            comps.sort(key=len, reverse=True)
            for comp in comps[1:]:
                r.add(ERROR, "DISCONNECTED", f"component not connected to main graph: {sorted(comp)}", ",".join(sorted(comp)))

    flow = ig.flow_graph()
    if flow.number_of_edges() and not nx.is_directed_acyclic_graph(flow):
        r.add(ERROR, "FLOW_CYCLE", "physical flow subgraph contains a cycle", "flow")

    dep = ig.dependency_graph()
    if dep.number_of_edges() and not nx.is_directed_acyclic_graph(dep):
        r.add(WARNING, "DEPENDENCY_CYCLE", "circular dependency present; confirm it is intended", "dependencies")

    flow_nodes = set(flow.nodes()) if flow.number_of_edges() else set()
    for n in ig.nodes:
        if n.zone == Zone.PHYSICAL and n.id not in flow_nodes and n.id in known:
            deg = flow.degree(n.id) if n.id in flow else 0
            if deg == 0:
                r.add(WARNING, "ORPHAN_PHYSICAL", "physical asset has no product-flow connection", n.id)
        if n.node_type in CONTROLLED_TYPES:
            has_ctrl = any(e.edge_type == EdgeType.CONTROL for _, _, e in ig._in_edges(n.id)) if n.id in g else False
            if not has_ctrl:
                r.add(WARNING, "UNCONTROLLED_ASSET", "pump/valve has no inbound control edge", n.id)

    if expected_zone_counts is not None:
        actual = ig.zone_counts()
        for z, want in expected_zone_counts.items():
            if actual.get(z, 0) != want:
                r.add(ERROR, "ZONE_COUNT", f"expected {want} nodes in {z.value}, found {actual.get(z, 0)}", z.value)

    return r
