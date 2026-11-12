import pytest

from impactgraph.infrastructure.enums import IsolationKind
from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.optimization import strategies as S
from impactgraph.simulation.monte_carlo import MonteCarloEngine
from impactgraph.simulation.propagation import PropagationModel
from impactgraph.simulation.scenarios import SCENARIOS

IG = build_phase1_topology()
MODEL = PropagationModel(IG)


def test_candidates_exclude_logical_isolation_into_safety_critical():
    for eid in S.candidate_edges(IG):
        e = IG.edge(eid)
        assert not (e.isolation_kind == IsolationKind.LOGICAL and IG.node(e.target).safety_critical)


def test_greedy_improves_objective_and_respects_constraints_s2():
    sc = SCENARIOS["S2"]
    g = S.greedy_isolation(IG, sc, MODEL, seed=5, trials=150)
    assert 0 < len(g.isolated) <= S.settings.MAX_ISOLATIONS
    assert not S.violates_constraints(IG, MODEL, g.isolated)
    ev = MonteCarloEngine(IG, sc, 200, 99, model=MODEL)
    base, _ = S.evaluate_strategy(IG, MODEL, sc, S.Strategy(S.NO_ISOLATION), ev)
    rec, _ = S.evaluate_strategy(IG, MODEL, sc, g, ev)
    assert rec.objective < base.objective and rec.throughput > base.throughput
    assert all(step["text"] for step in g.steps)          # every action carries an explanation


def test_greedy_is_deterministic():
    sc = SCENARIOS["S2"]
    a = S.greedy_isolation(IG, sc, MODEL, seed=3, trials=100).isolated
    b = S.greedy_isolation(IG, sc, MODEL, seed=3, trials=100).isolated
    assert a == b


def test_not_everything_is_isolated_and_continuity_holds():
    g = S.greedy_isolation(IG, SCENARIOS["S1"], MODEL, seed=1, trials=100)
    assert len(g.isolated) < len(S.candidate_edges(IG))
    assert MODEL.continuity_without_attack(g.isolated) >= S.settings.MIN_CONTINUITY


def test_constraint_violations_are_detected(monkeypatch):
    assert not S.violates_constraints(IG, MODEL, ("E19",))
    assert any(v.startswith("C3") for v in S.violates_constraints(IG, MODEL, tuple(f"E{i:02d}" for i in (1, 2, 3, 4, 5, 6, 7))))
    monkeypatch.setattr(S.settings, "MIN_CONTINUITY", 0.95)
    assert any(v.startswith("C2") for v in S.violates_constraints(IG, MODEL, ("E27",)))   # cutting SCADA->PLC lowers continuity


def test_full_shutdown_stops_throughput_and_costs_more_than_targeted():
    sc = SCENARIOS["S2"]
    ev = MonteCarloEngine(IG, sc, 150, 4, model=MODEL)
    shut, _ = S.evaluate_strategy(IG, MODEL, sc, S.Strategy(S.FULL_SHUTDOWN, shutdown=True), ev)
    tgt, _ = S.evaluate_strategy(IG, MODEL, sc, S.Strategy(S.IMPACTGRAPH, ("E19", "E20")), ev)
    assert shut.throughput == 0 and tgt.objective < shut.objective


def test_physical_valve_isolation_reduces_hazard_s3():
    sc = SCENARIOS["S3"]
    ev = MonteCarloEngine(IG, sc, 200, 4, model=MODEL)
    none, _ = S.evaluate_strategy(IG, MODEL, sc, S.Strategy(S.NO_ISOLATION), ev)
    valve, _ = S.evaluate_strategy(IG, MODEL, sc, S.Strategy(S.IMPACTGRAPH, ("E41",)), ev)
    assert valve.hazard < none.hazard
