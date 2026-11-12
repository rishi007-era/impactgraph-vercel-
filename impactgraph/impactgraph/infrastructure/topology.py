"""Phase 1 representative pipeline topology (24 components, Colonial-inspired).

This is a MODEL, not Colonial's real architecture. Importance, exposure,
vulnerability, traversal probabilities, dependency strengths and isolation costs
are assumed values for simulation and are not calibrated to any real system.
Flow capacities are in model units (m3/h), not real throughput.
"""
from __future__ import annotations

from .edges import Edge
from .enums import EdgeType as ET, IsolationKind, NodeType as NT, Zone
from .graph_builder import InfrastructureGraph
from .nodes import Node

PHASE1_ZONE_COUNTS = {Zone.VENDOR: 4, Zone.IT: 6, Zone.OT: 6, Zone.PHYSICAL: 8}

_CYBER_FEATS = ["cpu_util_pct", "net_traffic_mbps", "auth_events_per_min", "conn_per_min"]
_SERVER_FEATS = ["cpu_util_pct", "mem_util_pct", "net_traffic_mbps", "auth_events_per_min", "conn_per_min"]


def _nodes() -> list:
    N = Node
    return [
        # ---- Zone 1: vendor / external access (4)
        N("V01", "Vendor VPN Gateway", NT.VPN_GATEWAY, Zone.VENDOR, 0.35, 5.0, exposure=0.90, vulnerability=0.40,
          security_controls={"patched": True}, telemetry_features=_CYBER_FEATS,
          description="Remote-access VPN gateway used by vendors and contractors"),
        N("V02", "Legacy Remote Account", NT.REMOTE_ACCOUNT, Zone.VENDOR, 0.20, 5.0, exposure=0.85, vulnerability=0.70,
          security_controls={"mfa": False}, telemetry_features=["auth_events_per_min", "conn_per_min"],
          description="Contractor account without multi-factor authentication (modelled weakness)"),
        N("V03", "Remote Maintenance Portal", NT.REMOTE_PORTAL, Zone.VENDOR, 0.25, 5.0, exposure=0.70, vulnerability=0.50,
          telemetry_features=_CYBER_FEATS, description="Portal used for vendor maintenance sessions"),
        N("V04", "Managed Service Provider", NT.EXTERNAL_PROVIDER, Zone.VENDOR, 0.15, 5.0, exposure=0.50, vulnerability=0.40,
          telemetry_features=["net_traffic_mbps", "conn_per_min"], description="External IT/OT service provider"),
        # ---- Zone 2: enterprise IT (6)
        N("IT01", "Identity Service (Active Directory)", NT.IDENTITY_SERVICE, Zone.IT, 0.70, 4.0, exposure=0.20,
          vulnerability=0.35, physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS),
        N("IT02", "Billing Application Server", NT.APPLICATION_SERVER, Zone.IT, 0.55, 4.0, exposure=0.30,
          vulnerability=0.40, physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS,
          description="Billing and custody accounting application"),
        N("IT03", "Enterprise Database", NT.DATABASE, Zone.IT, 0.50, 4.0, exposure=0.10, vulnerability=0.30,
          physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS),
        N("IT04", "File Server", NT.FILE_SERVER, Zone.IT, 0.25, 4.0, exposure=0.10, vulnerability=0.35,
          physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS),
        N("IT05", "Backup System", NT.BACKUP_SYSTEM, Zone.IT, 0.40, 4.0, exposure=0.05, vulnerability=0.30,
          physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS),
        N("IT06", "Administrator Workstation", NT.ADMIN_WORKSTATION, Zone.IT, 0.35, 4.0, exposure=0.30,
          vulnerability=0.40, physical_access_exposure=0.10, telemetry_features=_CYBER_FEATS),
        # ---- Zone 3: operational technology (6)
        N("OT01", "IT/OT Gateway (DMZ)", NT.BOUNDARY_GATEWAY, Zone.OT, 0.80, 3.5, exposure=0.20, vulnerability=0.30,
          physical_access_exposure=0.05, security_controls={"firewall_rules": True, "allowlist": True},
          telemetry_features=["cpu_util_pct", "net_traffic_mbps", "conn_per_min"],
          description="Only permitted path between IT/vendor networks and OT"),
        N("OT02", "SCADA Server", NT.SCADA_SERVER, Zone.OT, 0.90, 2.0, exposure=0.05, vulnerability=0.30,
          physical_access_exposure=0.05, telemetry_features=_SERVER_FEATS),
        N("OT03", "Operator HMI", NT.HMI, Zone.OT, 0.60, 2.0, exposure=0.05, vulnerability=0.30,
          physical_access_exposure=0.10, telemetry_features=["cpu_util_pct", "auth_events_per_min"]),
        N("OT04", "Engineering Workstation", NT.ENGINEERING_WORKSTATION, Zone.OT, 0.50, 3.0, exposure=0.05,
          vulnerability=0.35, physical_access_exposure=0.10, telemetry_features=_CYBER_FEATS),
        N("OT05", "PLC - Pump Station 1", NT.PLC, Zone.OT, 0.85, 1.0, exposure=0.02, vulnerability=0.25,
          physical_access_exposure=0.30, telemetry_features=["cpu_util_pct", "conn_per_min"]),
        N("OT06", "RTU - Field Valves and Pump Station 2", NT.RTU, Zone.OT, 0.80, 1.0, exposure=0.02, vulnerability=0.30,
          physical_access_exposure=0.50, telemetry_features=["cpu_util_pct", "conn_per_min"],
          description="Phase 1 simplification: one field RTU cluster; split in Phase 2"),
        # ---- Zone 4: physical infrastructure (8)
        N("PH01", "Pump Station 1", NT.PUMP_STATION, Zone.PHYSICAL, 0.95, 0.0, physical_access_exposure=0.30,
          safety_critical=True, capacity_m3h=1000, vulnerability=0.10,
          telemetry_features=["pump_state", "pressure_bar", "flow_m3h", "temperature_c"]),
        N("PH02", "Pipeline Segment A", NT.PIPELINE_SEGMENT, Zone.PHYSICAL, 0.80, 0.0, physical_access_exposure=0.40,
          safety_critical=True, capacity_m3h=1000, vulnerability=0.10, telemetry_features=["pressure_bar", "flow_m3h"]),
        N("PH03", "Block Valve Station", NT.BLOCK_VALVE, Zone.PHYSICAL, 0.85, 0.0, physical_access_exposure=0.55,
          safety_critical=True, capacity_m3h=1000, vulnerability=0.10,
          telemetry_features=["valve_position_pct", "pressure_bar", "flow_m3h"]),
        N("PH04", "Pump Station 2", NT.PUMP_STATION, Zone.PHYSICAL, 0.95, 0.0, physical_access_exposure=0.30,
          safety_critical=True, capacity_m3h=1000, vulnerability=0.10,
          telemetry_features=["pump_state", "pressure_bar", "flow_m3h", "temperature_c"]),
        N("PH05", "Pipeline Segment B", NT.PIPELINE_SEGMENT, Zone.PHYSICAL, 0.80, 0.0, physical_access_exposure=0.40,
          safety_critical=True, capacity_m3h=1000, vulnerability=0.10, telemetry_features=["pressure_bar", "flow_m3h"]),
        N("PH06", "Storage Tank", NT.STORAGE_TANK, Zone.PHYSICAL, 0.60, 0.0, physical_access_exposure=0.20,
          safety_critical=True, capacity_m3h=500, vulnerability=0.10,
          telemetry_features=["tank_level_pct", "flow_m3h", "temperature_c"]),
        N("PH07", "Terminal", NT.TERMINAL, Zone.PHYSICAL, 0.90, 0.0, physical_access_exposure=0.15,
          capacity_m3h=1000, vulnerability=0.10, telemetry_features=["flow_m3h", "pressure_bar"]),
        N("PH08", "Delivery Point", NT.DELIVERY_POINT, Zone.PHYSICAL, 0.90, 0.0, physical_access_exposure=0.15,
          capacity_m3h=1000, vulnerability=0.10, telemetry_features=["flow_m3h"]),
    ]


def _edges() -> list:
    out: list = []
    LOG = IsolationKind.LOGICAL

    def add(src, dst, etype, imp, p=None, conds=(), cost=0.0, kind=None, **kw):
        iso = cost > 0
        out.append(Edge(
            id=f"E{len(out) + 1:02d}", source=src, target=dst, edge_type=etype, importance=imp,
            traversal_probability=p, access_conditions=list(conds),
            isolatable=iso, isolation_kind=(kind or LOG) if iso else None, isolation_cost=cost, **kw))

    # --- vendor access and ingress
    add("V04", "V01", ET.NETWORK, 0.30, 0.35, ["network_reachability", "valid_credentials"], 0.5)
    add("V02", "V01", ET.AUTH, 0.50, 0.70, ["valid_credentials", "mfa_absent_or_bypassed"], 0.5,
        description="Legacy account authenticates to the VPN gateway")
    add("V04", "V03", ET.NETWORK, 0.30, 0.35, ["network_reachability", "valid_credentials"], 0.5)
    add("V03", "OT01", ET.NETWORK, 0.40, 0.12, ["maintenance_session_active", "boundary_rule_permits"], 1.0,
        description="Maintenance sessions terminate at the DMZ gateway (hypothetical exposure path)")
    add("V01", "IT01", ET.NETWORK, 0.60, 0.55, ["network_reachability"], 2.0)
    add("V01", "IT02", ET.NETWORK, 0.40, 0.35, ["network_reachability"], 1.5)
    add("V01", "IT06", ET.NETWORK, 0.30, 0.30, ["network_reachability"], 1.0)
    add("IT01", "V01", ET.SERVICE_DEP, 0.70, dependency_strength=0.80,
        description="VPN authentication depends on the identity service")
    # --- enterprise IT
    add("IT01", "IT02", ET.AUTH, 0.60, 0.60, ["valid_credentials", "domain_trust"], 2.5)
    add("IT01", "IT03", ET.AUTH, 0.60, 0.50, ["valid_credentials", "domain_trust"], 2.5)
    add("IT01", "IT04", ET.AUTH, 0.40, 0.50, ["valid_credentials", "domain_trust"], 1.5)
    add("IT01", "IT05", ET.AUTH, 0.50, 0.35, ["valid_credentials", "admin_privilege"], 1.5)
    add("IT01", "IT06", ET.AUTH, 0.40, 0.55, ["valid_credentials", "domain_trust"], 1.5)
    add("IT02", "IT03", ET.NETWORK, 0.60, 0.60, ["network_reachability"], 2.0)
    add("IT06", "IT04", ET.NETWORK, 0.30, 0.50, ["network_reachability", "valid_credentials"], 0.8)
    add("IT04", "IT05", ET.NETWORK, 0.30, 0.35, ["network_reachability", "valid_credentials"], 0.8)
    add("IT03", "IT02", ET.SERVICE_DEP, 0.70, dependency_strength=0.90)
    add("IT01", "IT02", ET.SERVICE_DEP, 0.60, dependency_strength=0.70)
    # --- IT/OT boundary (the DMZ gateway is the only legal crossing)
    add("IT06", "OT01", ET.NETWORK, 0.50, 0.20, ["admin_privilege", "boundary_rule_permits"], 1.0)
    add("IT01", "OT01", ET.AUTH, 0.40, 0.12, ["domain_trust", "boundary_rule_permits"], 1.0,
        description="Shared identity trust across the boundary (hypothetical weakness)")
    add("IT02", "PH08", ET.OPERATIONAL_DEP, 0.50, dependency_strength=0.50,
        description="Reconstructed assumption: custody/billing needed to complete deliveries")
    # --- operational technology
    add("OT01", "OT02", ET.NETWORK, 0.80, 0.35, ["boundary_rule_permits", "network_reachability"], 3.0)
    add("OT01", "OT04", ET.NETWORK, 0.50, 0.25, ["boundary_rule_permits", "valid_credentials"], 1.5)
    add("OT02", "OT03", ET.NETWORK, 0.60, 0.60, ["network_reachability"], 2.0)
    add("OT04", "OT02", ET.NETWORK, 0.50, 0.40, ["network_reachability", "engineering_privilege"], 1.0)
    add("OT03", "OT02", ET.CONTROL, 0.60, 0.50, ["valid_credentials", "controller_write_access"])
    add("OT02", "OT05", ET.CONTROL, 0.80, 0.50, ["controller_write_access", "network_reachability"], 4.0)
    add("OT02", "OT06", ET.CONTROL, 0.80, 0.50, ["controller_write_access", "network_reachability"], 4.0)
    add("OT04", "OT05", ET.CONTROL, 0.60, 0.45, ["engineering_privilege", "controller_write_access"], 1.0)
    add("OT04", "OT06", ET.CONTROL, 0.60, 0.40, ["engineering_privilege", "controller_write_access"], 1.0)
    add("OT02", "OT03", ET.SERVICE_DEP, 0.60, dependency_strength=0.90)
    add("OT02", "OT05", ET.OPERATIONAL_DEP, 0.50, dependency_strength=0.30,
        description="Controller can run local logic without SCADA; supervision lost")
    add("OT02", "OT06", ET.OPERATIONAL_DEP, 0.50, dependency_strength=0.30)
    # --- actuation: controller -> physical asset (cyber-physical effect) and operating dependency
    add("OT05", "PH01", ET.CONTROL, 0.90, 0.70, ["controller_write_access"],
        description="Probability that controller compromise leads to unsafe actuation (assumed)")
    add("OT06", "PH03", ET.CONTROL, 0.90, 0.70, ["controller_write_access"])
    add("OT06", "PH04", ET.CONTROL, 0.90, 0.60, ["controller_write_access"])
    add("OT06", "PH06", ET.CONTROL, 0.60, 0.50, ["controller_write_access"])
    add("OT05", "PH01", ET.OPERATIONAL_DEP, 0.90, dependency_strength=0.90)
    add("OT06", "PH03", ET.OPERATIONAL_DEP, 0.90, dependency_strength=0.90)
    add("OT06", "PH04", ET.OPERATIONAL_DEP, 0.90, dependency_strength=0.90)
    # --- physical product flow (capacities in model units, m3/h)
    add("PH01", "PH02", ET.PHYSICAL_FLOW, 0.90, flow_capacity_m3h=1000, cost=3.0, kind=IsolationKind.PHYSICAL,
        description="Pump-station discharge isolation valve (reactive)")
    add("PH02", "PH03", ET.PHYSICAL_FLOW, 0.90, flow_capacity_m3h=1000, cost=3.0, kind=IsolationKind.PHYSICAL,
        description="Isolatable by closing the upstream block valve (reactive; low marginal cost on an already stopped line)")
    add("PH03", "PH04", ET.PHYSICAL_FLOW, 0.90, flow_capacity_m3h=1000, cost=3.0, kind=IsolationKind.PHYSICAL)
    add("PH04", "PH05", ET.PHYSICAL_FLOW, 0.90, flow_capacity_m3h=1000)
    add("PH05", "PH06", ET.PHYSICAL_FLOW, 0.60, flow_capacity_m3h=500)
    add("PH05", "PH07", ET.PHYSICAL_FLOW, 0.80, flow_capacity_m3h=500)
    add("PH06", "PH07", ET.PHYSICAL_FLOW, 0.60, flow_capacity_m3h=400)
    add("PH07", "PH08", ET.PHYSICAL_FLOW, 0.90, flow_capacity_m3h=1000)
    return out


def build_phase1_topology() -> InfrastructureGraph:
    """Return the validated-by-construction 24-node Phase 1 infrastructure graph."""
    return InfrastructureGraph("phase1_pipeline", _nodes(), _edges())
