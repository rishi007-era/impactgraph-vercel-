import copy

import networkx as nx
import pytest

from impactgraph.infrastructure.edges import Edge
from impactgraph.infrastructure.enums import (ATTACK_TRAVERSABLE, EdgeType as ET, IsolationKind,
                                              NodeType as NT, Zone, Criticality)
from impactgraph.infrastructure.graph_builder import InfrastructureGraph
from impactgraph.infrastructure.graph_validator import validate_graph
from impactgraph.infrastructure.nodes import Node, criticality_from_importance
from impactgraph.infrastructure.topology import PHASE1_ZONE_COUNTS, build_phase1_topology


@pytest.fixture
def ig():
    return build_phase1_topology()


def _with_extra_edge(ig, **kw):
    g2 = ig.copy()
    defaults = dict(id="EX1", importance=0.5)
    defaults.update(kw)
    g2.edges.append(Edge(**defaults))
    g2._rebuild()
    return g2


# ---------- baseline topology ----------
def test_phase1_counts(ig):
    assert len(ig.nodes) == 24
    assert ig.zone_counts() == PHASE1_ZONE_COUNTS
    assert 35 <= len(ig.edges) <= 55


def test_baseline_validates_clean(ig):
    r = validate_graph(ig, PHASE1_ZONE_COUNTS)
    assert r.ok, [str(i) for i in r.errors]
    assert not r.warnings, [str(i) for i in r.warnings]


def test_all_relationship_types_used(ig):
    assert {e.edge_type for e in ig.edges} == set(ET)


def test_graph_is_connected(ig):
    assert nx.is_weakly_connected(ig.g)


def test_criticality_mapping():
    assert criticality_from_importance(0.9) == Criticality.CRITICAL
    assert criticality_from_importance(0.6) == Criticality.HIGH
    assert criticality_from_importance(0.3) == Criticality.MEDIUM
    assert criticality_from_importance(0.1) == Criticality.LOW


# ---------- relationship types are never mixed ----------
def test_attack_graph_excludes_flow_and_dependencies(ig):
    types = {d["data"].edge_type for *_, d in ig.attack_graph().edges(keys=True, data=True)}
    assert types == set(ATTACK_TRAVERSABLE)


def test_flow_graph_is_physical_only_and_acyclic(ig):
    fg = ig.flow_graph()
    assert all(ig.node(n).zone == Zone.PHYSICAL for n in fg.nodes if fg.degree(n) > 0)
    assert nx.is_directed_acyclic_graph(fg)


def test_no_attack_path_edge_enters_physical_except_control(ig):
    for e in ig.edges:
        if ig.node(e.target).zone == Zone.PHYSICAL and e.is_attack_traversable:
            assert e.edge_type == ET.CONTROL and ig.node(e.source).zone == Zone.OT


def test_vendor_reaches_ot_only_through_gateway(ig):
    for e in ig.attack_graph().edges(data=True):
        pass
    for e in ig.edges:
        if e.is_attack_traversable and ig.node(e.source).zone in (Zone.VENDOR, Zone.IT) \
                and ig.node(e.target).zone == Zone.OT:
            assert ig.node(e.target).node_type == NT.BOUNDARY_GATEWAY


def test_physical_path_from_vendor_exists_in_attack_graph(ig):
    ag = ig.attack_graph()
    assert nx.has_path(ag, "V02", "PH01")  # vendor account -> ... -> pump station 1 (hypothetical)


def test_dependencies_queries(ig):
    deps = {e.source for e in ig.dependencies_of("PH01")}
    assert deps == {"OT05"}
    assert {e.target for e in ig.dependents_of("OT02")} == {"OT03", "OT05", "OT06"}


# ---------- validator catches bad models ----------
def test_detects_invalid_reference(ig):
    g2 = _with_extra_edge(ig, source="V01", target="NOPE", edge_type=ET.NETWORK,
                          traversal_probability=0.5, access_conditions=["network_reachability"])
    assert "INVALID_REFERENCE" in validate_graph(g2).codes()


def test_detects_duplicate_ids(ig):
    g2 = ig.copy()
    g2.nodes.append(copy.deepcopy(g2.nodes[0]))
    g2._rebuild()
    assert "DUP_NODE_ID" in validate_graph(g2).codes()


def test_detects_self_loop(ig):
    g2 = _with_extra_edge(ig, source="IT01", target="IT01", edge_type=ET.AUTH,
                          traversal_probability=0.5, access_conditions=["valid_credentials"])
    assert "SELF_LOOP" in validate_graph(g2).codes()


def test_detects_disconnected_node(ig):
    g2 = ig.copy()
    g2.nodes.append(Node("IT99", "Orphan", NT.FILE_SERVER, Zone.IT, 0.1, 4.0))
    g2._rebuild()
    assert "DISCONNECTED" in validate_graph(g2).codes()


def test_detects_flow_cycle(ig):
    g2 = _with_extra_edge(ig, source="PH08", target="PH01", edge_type=ET.PHYSICAL_FLOW, flow_capacity_m3h=100)
    assert "FLOW_CYCLE" in validate_graph(g2).codes()


def test_flow_between_non_physical_rejected(ig):
    g2 = _with_extra_edge(ig, source="IT01", target="IT03", edge_type=ET.PHYSICAL_FLOW, flow_capacity_m3h=100)
    assert "EDGE_TYPE_ENDPOINTS" in validate_graph(g2).codes()


def test_vendor_direct_to_scada_rejected(ig):
    g2 = _with_extra_edge(ig, source="V01", target="OT02", edge_type=ET.NETWORK,
                          traversal_probability=0.5, access_conditions=["network_reachability"])
    assert "UNREALISTIC_CROSS_ZONE" in validate_graph(g2).codes()


def test_it_direct_to_plc_rejected(ig):
    g2 = _with_extra_edge(ig, source="IT06", target="OT05", edge_type=ET.NETWORK,
                          traversal_probability=0.5, access_conditions=["network_reachability"])
    assert "UNREALISTIC_CROSS_ZONE" in validate_graph(g2).codes()


def test_network_edge_into_physical_rejected(ig):
    g2 = _with_extra_edge(ig, source="OT02", target="PH01", edge_type=ET.NETWORK,
                          traversal_probability=0.5, access_conditions=["network_reachability"])
    assert "EDGE_TYPE_ENDPOINTS" in validate_graph(g2).codes()


def test_traversal_probability_on_flow_edge_rejected(ig):
    g2 = _with_extra_edge(ig, source="PH01", target="PH03", edge_type=ET.PHYSICAL_FLOW,
                          flow_capacity_m3h=10, traversal_probability=0.5)
    assert "EDGE_FIELD" in validate_graph(g2).codes()


def test_unknown_access_condition_rejected(ig):
    g2 = _with_extra_edge(ig, source="V04", target="IT01", edge_type=ET.NETWORK,
                          traversal_probability=0.5, access_conditions=["magic"])
    assert "EDGE_FIELD" in validate_graph(g2).codes()


def test_out_of_range_node_values_rejected(ig):
    g2 = ig.copy()
    g2.nodes[0].exposure = 1.7
    assert "NODE_FIELD" in validate_graph(g2).codes()


def test_node_in_wrong_zone_rejected(ig):
    g2 = ig.copy()
    g2.node("IT03").zone = Zone.OT
    assert "NODE_TYPE_ZONE" in validate_graph(g2).codes()


def test_zone_count_mismatch_reported(ig):
    wrong = dict(PHASE1_ZONE_COUNTS)
    wrong[Zone.IT] = 7
    assert "ZONE_COUNT" in validate_graph(ig, wrong).codes()


def test_logical_isolation_into_safety_critical_warns(ig):
    g2 = _with_extra_edge(ig, source="OT04", target="PH02", edge_type=ET.CONTROL,
                          traversal_probability=0.3, access_conditions=["controller_write_access"],
                          isolatable=True, isolation_kind=IsolationKind.LOGICAL, isolation_cost=1.0)
    assert "SAFETY_REVIEW" in validate_graph(g2).codes()


def test_dependency_cannot_be_isolatable(ig):
    g2 = _with_extra_edge(ig, source="IT04", target="IT02", edge_type=ET.SERVICE_DEP,
                          dependency_strength=0.2, isolatable=True,
                          isolation_kind=IsolationKind.LOGICAL, isolation_cost=1.0)
    assert "EDGE_FIELD" in validate_graph(g2).codes()


# ---------- persistence ----------
def test_json_round_trip(ig):
    ig2 = InfrastructureGraph.from_json(ig.to_json())
    assert ig2.summary() == ig.summary()
    assert validate_graph(ig2, PHASE1_ZONE_COUNTS).ok
    assert ig2.node("V02").security_controls == {"mfa": False}
    assert ig2.edge("E02").isolation_kind == IsolationKind.LOGICAL


def test_copy_is_independent(ig):
    c = ig.copy()
    c.node("PH01").current_condition = c.node("PH01").current_condition.__class__.FAILED
    assert ig.node("PH01").current_condition.value == "normal"
