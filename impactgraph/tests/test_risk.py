import pytest

from impactgraph.config import settings
from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.risk.risk_scoring import risk_table
from impactgraph.risk.criticality import downstream_share, single_points_of_failure
from impactgraph.simulation.propagation import PropagationModel

IG = build_phase1_topology()


def test_weights_sum_to_one():
    assert sum(settings.RISK_LIKELIHOOD_WEIGHTS.values()) == pytest.approx(1)
    assert sum(settings.RISK_CONSEQUENCE_WEIGHTS.values()) == pytest.approx(1)
    assert sum(settings.IMPACT_WEIGHTS.values()) == pytest.approx(1)


def test_risk_is_normalised_and_sorted_and_follows_formula():
    freq = {n.id: 0.5 for n in IG.nodes}
    df = risk_table(IG, freq, {"OT02": 0.9}, {"IT01": 0.8})
    assert df.risk.between(0, 1).all() and df.risk.is_monotonic_decreasing
    r = df.set_index("component_id").loc["OT02"]
    assert r.risk == pytest.approx(r.likelihood * r.consequence)
    assert r.evidence == pytest.approx(0.9)


def test_centrality_is_supplementary_not_an_input():
    freq = {n.id: 0.0 for n in IG.nodes}
    df = risk_table(IG, freq, {}, {})
    assert (df.betweenness >= 0).all()
    base = df.set_index("component_id").risk.to_dict()
    df2 = risk_table(IG, freq, {}, {})
    assert base == df2.set_index("component_id").risk.to_dict()


def test_downstream_share_and_spof():
    D = downstream_share(IG)
    assert D["OT02"] > D["PH08"] and D["PH08"] == 0
    spof = single_points_of_failure(IG, PropagationModel(IG))
    assert "PH01" in spof and "PH04" in spof and "IT04" not in spof
