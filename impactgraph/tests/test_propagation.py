import pytest

from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.simulation.propagation import PropagationModel


@pytest.fixture(scope="module")
def ctx():
    ig = build_phase1_topology()
    return ig, PropagationModel(ig)


def test_baseline_throughput_and_no_loss(ctx):
    ig, m = ctx
    assert m.baseline_throughput == 900
    c = m.evaluate(frozenset())
    assert c.throughput_fraction == pytest.approx(1.0) and c.service_loss == 0 and c.impact == 0


def test_controller_failure_propagates_to_pump(ctx):
    ig, m = ctx
    c = m.evaluate(frozenset({"OT05"}))
    assert c.services["PH01"] == pytest.approx(0.1)           # 1 - 0.9*(1-0) via operational dependency
    assert c.throughput_fraction < 0.2


def test_billing_dependency_is_partial(ctx):
    ig, m = ctx
    c = m.evaluate(frozenset({"IT02"}))
    assert c.services["PH08"] == pytest.approx(0.5) and 0.4 < c.throughput_fraction < 0.7


def test_tank_failure_keeps_partial_throughput(ctx):
    ig, m = ctx
    assert m.evaluate(frozenset({"PH06"})).throughput_fraction == pytest.approx(500 / 900)


def test_service_levels_never_exceed_one_and_failed_is_zero(ctx):
    ig, m = ctx
    c = m.evaluate(frozenset({"IT01", "OT02", "PH04"}))
    assert all(0 <= v <= 1 for v in c.services.values())
    assert c.services["IT01"] == 0 and c.services["PH04"] == 0


def test_isolating_a_link_severs_its_dependency(ctx):
    ig, m = ctx
    sev = m.severed_dependencies({"E27"})                      # SCADA -> PLC1 control link
    assert any(ig.edge(d).target == "OT05" for d in sev)
    assert m.continuity_without_attack({"E27"}) < 1.0
    assert m.continuity_without_attack({"E22"}) == pytest.approx(1.0)   # DMZ link: no operating dependency


def test_release_hazard_and_valve_closure(ctx):
    ig, m = ctx
    open_ = m.evaluate(frozenset({"PH05"}), release=frozenset({"PH05"}))
    closed = m.evaluate(frozenset({"PH05"}), closed=frozenset({"E43"}), release=frozenset({"PH05"}))
    assert open_.hazard == pytest.approx(1.0) and closed.hazard == 0.0


def test_physical_flow_never_creates_attack_edges(ctx):
    ig, _ = ctx
    from impactgraph.infrastructure.enums import EdgeType
    assert all(e.edge_type != EdgeType.PHYSICAL_FLOW for _, _, _, d in ig.attack_graph().edges(keys=True, data=True) for e in [d["data"]])
