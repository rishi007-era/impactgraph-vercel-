"""Node schema for the infrastructure graph."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .enums import ComponentCategory, Condition, Criticality, NodeType, Zone
from .telemetry_spec import TELEMETRY_FEATURES

# node type -> (category, allowed zones)
TYPE_RULES: dict = {
    NodeType.VPN_GATEWAY: (ComponentCategory.ACCESS, frozenset({Zone.VENDOR})),
    NodeType.REMOTE_ACCOUNT: (ComponentCategory.ACCESS, frozenset({Zone.VENDOR})),
    NodeType.REMOTE_PORTAL: (ComponentCategory.ACCESS, frozenset({Zone.VENDOR})),
    NodeType.EXTERNAL_PROVIDER: (ComponentCategory.ACCESS, frozenset({Zone.VENDOR})),
    NodeType.IDENTITY_SERVICE: (ComponentCategory.IT_SERVICE, frozenset({Zone.IT})),
    NodeType.APPLICATION_SERVER: (ComponentCategory.IT_SERVICE, frozenset({Zone.IT})),
    NodeType.DATABASE: (ComponentCategory.IT_SERVICE, frozenset({Zone.IT})),
    NodeType.FILE_SERVER: (ComponentCategory.IT_SERVICE, frozenset({Zone.IT})),
    NodeType.BACKUP_SYSTEM: (ComponentCategory.IT_SERVICE, frozenset({Zone.IT})),
    NodeType.ADMIN_WORKSTATION: (ComponentCategory.IT_ENDPOINT, frozenset({Zone.IT})),
    NodeType.BOUNDARY_GATEWAY: (ComponentCategory.OT_BOUNDARY, frozenset({Zone.OT})),
    NodeType.SCADA_SERVER: (ComponentCategory.OT_SUPERVISORY, frozenset({Zone.OT})),
    NodeType.HMI: (ComponentCategory.OT_SUPERVISORY, frozenset({Zone.OT})),
    NodeType.ENGINEERING_WORKSTATION: (ComponentCategory.OT_SUPERVISORY, frozenset({Zone.OT})),
    NodeType.PLC: (ComponentCategory.OT_CONTROLLER, frozenset({Zone.OT})),
    NodeType.RTU: (ComponentCategory.OT_CONTROLLER, frozenset({Zone.OT})),
    NodeType.PUMP_STATION: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
    NodeType.PIPELINE_SEGMENT: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
    NodeType.BLOCK_VALVE: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
    NodeType.STORAGE_TANK: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
    NodeType.TERMINAL: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
    NodeType.DELIVERY_POINT: (ComponentCategory.PROCESS_ASSET, frozenset({Zone.PHYSICAL})),
}

# Types that need a controlling OT component (checked as a warning by the validator)
CONTROLLED_TYPES = frozenset({NodeType.PUMP_STATION, NodeType.BLOCK_VALVE})


def criticality_from_importance(importance: float) -> Criticality:
    """Documented mapping from operational importance (0..1) to a criticality level."""
    if importance >= 0.85:
        return Criticality.CRITICAL
    if importance >= 0.60:
        return Criticality.HIGH
    if importance >= 0.30:
        return Criticality.MEDIUM
    return Criticality.LOW


@dataclass
class Node:
    id: str
    name: str
    node_type: NodeType
    zone: Zone
    operational_importance: float          # 0..1, assumed
    purdue_level: float                    # 0..5 (3.5 = IT/OT DMZ), reference model level
    exposure: float = 0.0                  # 0..1 remote/external reachability (assumed)
    vulnerability: float = 0.0             # 0..1 weakness of the component (assumed)
    physical_access_exposure: float = 0.0  # 0..1 ease of unauthorised on-site access (assumed)
    safety_critical: bool = False
    capacity_m3h: Optional[float] = None   # throughput capacity, physical nodes only (model units)
    security_controls: dict = field(default_factory=dict)
    telemetry_features: list = field(default_factory=list)
    initial_condition: Condition = Condition.NORMAL
    current_condition: Condition = Condition.NORMAL
    description: str = ""

    @property
    def category(self) -> ComponentCategory:
        return TYPE_RULES[self.node_type][0]

    @property
    def criticality(self) -> Criticality:
        return criticality_from_importance(self.operational_importance)

    def validate(self) -> list:
        problems: list = []
        if not self.id or not self.id.strip():
            problems.append("empty id")
        if not self.name:
            problems.append("empty name")
        for fname in ("operational_importance", "exposure", "vulnerability", "physical_access_exposure"):
            v = getattr(self, fname)
            if not (0.0 <= v <= 1.0):
                problems.append(f"{fname}={v} outside [0,1]")
        if not (0.0 <= self.purdue_level <= 5.0):
            problems.append(f"purdue_level={self.purdue_level} outside [0,5]")
        if self.zone == Zone.PHYSICAL:
            if self.capacity_m3h is None or self.capacity_m3h <= 0:
                problems.append("physical node needs capacity_m3h > 0")
        elif self.capacity_m3h is not None:
            problems.append("capacity_m3h is only valid on physical nodes")
        for feat in self.telemetry_features:
            if feat not in TELEMETRY_FEATURES:
                problems.append(f"unknown telemetry feature '{feat}'")
        return problems

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("node_type", "zone", "initial_condition", "current_condition"):
            d[k] = d[k].value if hasattr(d[k], "value") else d[k]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        d = dict(d)
        d["node_type"] = NodeType(d["node_type"])
        d["zone"] = Zone(d["zone"])
        d["initial_condition"] = Condition(d.get("initial_condition", "normal"))
        d["current_condition"] = Condition(d.get("current_condition", "normal"))
        return cls(**d)
