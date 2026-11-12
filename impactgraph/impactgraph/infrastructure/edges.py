"""Edge schema for the infrastructure graph."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .enums import ATTACK_TRAVERSABLE, DEPENDENCY_TYPES, EdgeType, IsolationKind

# Controlled vocabulary for access conditions (extend deliberately, not ad hoc).
ACCESS_CONDITION_VOCAB = frozenset({
    "valid_credentials",
    "mfa_absent_or_bypassed",
    "network_reachability",
    "admin_privilege",
    "domain_trust",
    "boundary_rule_permits",
    "maintenance_session_active",
    "engineering_privilege",
    "controller_write_access",
})


@dataclass
class Edge:
    id: str
    source: str
    target: str
    edge_type: EdgeType
    importance: float                                  # 0..1 connection/dependency importance
    traversal_probability: Optional[float] = None      # NETWORK/AUTH/CONTROL only; assumed
    dependency_strength: Optional[float] = None        # SERVICE_DEP/OPERATIONAL_DEP only
    flow_capacity_m3h: Optional[float] = None          # PHYSICAL_FLOW only (model units)
    access_conditions: list = field(default_factory=list)
    isolatable: bool = False
    isolation_kind: Optional[IsolationKind] = None
    isolation_cost: float = 0.0                        # relative cost of isolating (assumed)
    description: str = ""

    # Edges are always directed; see the direction convention in enums.py.
    @property
    def is_attack_traversable(self) -> bool:
        return self.edge_type in ATTACK_TRAVERSABLE

    @property
    def is_dependency(self) -> bool:
        return self.edge_type in DEPENDENCY_TYPES

    def validate(self) -> list:
        p: list = []
        if not (0.0 <= self.importance <= 1.0):
            p.append(f"importance={self.importance} outside [0,1]")
        if self.is_attack_traversable:
            if self.traversal_probability is None or not (0.0 < self.traversal_probability <= 1.0):
                p.append("attack-traversable edge needs traversal_probability in (0,1]")
            if not self.access_conditions:
                p.append("attack-traversable edge needs at least one access condition")
        elif self.traversal_probability is not None:
            p.append(f"{self.edge_type.value} edge must not carry traversal_probability")
        if self.is_dependency:
            if self.dependency_strength is None or not (0.0 < self.dependency_strength <= 1.0):
                p.append("dependency edge needs dependency_strength in (0,1]")
        elif self.dependency_strength is not None:
            p.append(f"{self.edge_type.value} edge must not carry dependency_strength")
        if self.edge_type == EdgeType.PHYSICAL_FLOW:
            if self.flow_capacity_m3h is None or self.flow_capacity_m3h <= 0:
                p.append("physical_flow edge needs flow_capacity_m3h > 0")
            if self.access_conditions:
                p.append("physical_flow edge cannot have cyber access conditions")
        elif self.flow_capacity_m3h is not None:
            p.append("flow_capacity_m3h only valid on physical_flow edges")
        for c in self.access_conditions:
            if c not in ACCESS_CONDITION_VOCAB:
                p.append(f"unknown access condition '{c}'")
        if self.isolatable:
            if self.isolation_kind is None:
                p.append("isolatable edge needs isolation_kind")
            if self.isolation_cost <= 0:
                p.append("isolatable edge needs isolation_cost > 0")
            if self.is_dependency:
                p.append("a dependency cannot be 'isolated'; isolate the underlying link instead")
        else:
            if self.isolation_kind is not None:
                p.append("isolation_kind set on a non-isolatable edge")
        return p

    def to_dict(self) -> dict:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value
        d["isolation_kind"] = self.isolation_kind.value if self.isolation_kind else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        d = dict(d)
        d["edge_type"] = EdgeType(d["edge_type"])
        if d.get("isolation_kind"):
            d["isolation_kind"] = IsolationKind(d["isolation_kind"])
        return cls(**d)
