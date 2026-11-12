import numpy as np
import pytest

from impactgraph.attack_analysis.attack_model import AttackModel
from impactgraph.attack_analysis.path_analysis import top_paths
from impactgraph.infrastructure.enums import Zone
from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.simulation.monte_carlo import MonteCarloEngine
from impactgraph.simulation.scenarios import SCENARIOS, Scenario

IG = build_phase1_topology()


def _trial(sc, u=0.0, isolated=frozenset(), tau=None, foot=1.0):
    am = AttackModel(IG, sc)
    ue = np.full(am.n_attack_edges(), u)
    return am.run_trial(ue, np.full(len(IG.nodes), 1.0), np.ones(max(1, len(sc.physical_entries))), foot, isolated, tau)


def test_mode_a_attacker_stays_out_of_ot_without_foothold():
    out = _trial(SCENARIOS["S1"], u=0.0, foot=1.0)       # u=0 -> every attempted edge succeeds; foot=1.0 -> no foothold
    zones = {IG.node(n).zone for n in out.compromised}
    assert zones <= {Zone.VENDOR, Zone.IT} and not out.failed.keys() & {"PH01"}


def test_unrestricted_attack_reaches_physical_effect_when_all_succeed():
    out = _trial(SCENARIOS["S2"], u=0.0)
    assert "OT05" in out.compromised and out.failed["PH01"][1] == "actuation"


def test_conditions_gate_traversal():
    # a vendor-portal entry cannot cross into OT: maintenance session is inactive by default
    sc = Scenario(id="X", name="x", mode="B", description="", entry_nodes=(("V03", frozenset({"valid_credentials"})),))
    out = _trial(sc, u=0.0)
    assert "OT01" not in out.compromised
    sc2 = Scenario(id="Y", name="y", mode="B", description="", entry_nodes=(("V03", frozenset({"valid_credentials"})),),
                   env={"maintenance_session_active": True})
    assert "OT01" in _trial(sc2, u=0.0).compromised


def test_unreachable_when_probabilities_fail():
    out = _trial(SCENARIOS["S2"], u=0.999999)
    assert set(out.compromised) == {"V02"}


def test_isolation_blocks_transitions_completing_after_response_time():
    sc = SCENARIOS["S2"]
    blocked = _trial(sc, u=0.0, isolated=frozenset({"E19", "E20"}), tau=0.0)
    assert "OT01" not in blocked.compromised
    late = _trial(sc, u=0.0, isolated=frozenset({"E19", "E20"}), tau=1000.0)
    assert "OT01" in late.compromised


def test_monte_carlo_is_reproducible_and_common_random_numbers():
    sc = SCENARIOS["S2"]
    a = MonteCarloEngine(IG, sc, 200, 11).run()
    b = MonteCarloEngine(IG, sc, 200, 11).run()
    assert np.allclose(a.impact, b.impact)
    eng = MonteCarloEngine(IG, sc, 200, 11)
    assert eng.run().mean("impact") >= eng.run(isolated={"E19", "E20"}).mean("impact")


def test_attack_paths_explain_feasibility_and_cross_boundary_only_via_gateway():
    paths = top_paths(IG, SCENARIOS["S2"], "V02", "PH01", k=2)
    assert paths and paths[0]["nodes"][0] == "V02" and paths[0]["nodes"][-1] == "PH01"
    assert "OT01" in paths[0]["nodes"] and all(h["feasible"] for h in paths[0]["hops"])
    assert all(0 < p["probability"] < 1 for p in paths)
