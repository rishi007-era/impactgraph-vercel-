"""Stochastic attack-propagation model (independent-cascade style with access preconditions).

For every attack-traversable edge u -> v:
  * the edge may be attempted only after u is compromised AND all its access conditions hold;
  * the adversary has `attempts` tries; success probability within them is p_total = 1 - (1 - p)^attempts;
  * on success the attempt index k (1..attempts) is the number of hops the transition takes;
  * a CONTROL edge into a physical asset models unsafe actuation: the asset is FAILED, not 'compromised';
  * isolation decided at response time `tau` blocks any transition that would COMPLETE after tau;
  * the attacker may be restricted to some zones (Mode A: no OT movement).

Random numbers are supplied per trial (common random numbers) so that different isolation sets
can be compared without simulation noise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..infrastructure.enums import EdgeType, NodeType, Zone
from ..infrastructure.graph_builder import InfrastructureGraph
from ..simulation.scenarios import Scenario
from .access_rules import DEFAULT_ENV, caps_for, condition_status

RELEASE_TYPES = {NodeType.PIPELINE_SEGMENT, NodeType.STORAGE_TANK}


@dataclass
class TrialOutcome:
    compromised: dict = field(default_factory=dict)      # node -> time (hops)
    failed: dict = field(default_factory=dict)           # node -> (time, kind)
    used_edges: list = field(default_factory=list)       # (edge_id, t_start, t_end)
    release: frozenset = frozenset()
    foothold: bool = False


class AttackModel:
    def __init__(self, ig: InfrastructureGraph, scenario: Scenario):
        self.ig, self.sc = ig, scenario
        self.env = dict(DEFAULT_ENV)
        self.env.update(scenario.env)
        self.attack_edges = [e for e in ig.edges if e.is_attack_traversable]
        self.edge_index = {e.id: i for i, e in enumerate(self.attack_edges)}
        self.node_index = {n.id: i for i, n in enumerate(ig.nodes)}
        self.out = {n.id: [] for n in ig.nodes}
        for e in self.attack_edges:
            self.out[e.source].append(e)
        self.phys_entries = list(scenario.physical_entries)

    @staticmethod
    def p_total(p: float, attempts: int) -> float:
        return 1.0 - (1.0 - p) ** attempts

    @staticmethod
    def attempt_index(u: float, p: float) -> int:
        if p >= 1.0:
            return 1
        return max(1, math.ceil(math.log(1.0 - u) / math.log(1.0 - p)))

    def n_attack_edges(self) -> int:
        return len(self.attack_edges)

    def run_trial(self, u_edge, u_ransom, u_phys, u_foot, isolated=frozenset(), tau=None, prob_scale=None) -> TrialOutcome:
        sc, ig, K = self.sc, self.ig, self.sc.attempts
        tau = sc.response_delay if tau is None else tau
        out = TrialOutcome()
        out.foothold = bool(sc.ot_foothold_prob > 0 and u_foot < sc.ot_foothold_prob)
        allowed = None if (out.foothold or sc.allowed_zones is None) else sc.allowed_zones
        comp: dict = {}
        failed: dict = {}
        release = set()

        def zone_ok(nid):
            return allowed is None or ig.node(nid).zone in allowed

        for nid, caps in sc.entry_nodes:
            comp[nid] = 0.0
        if out.foothold:
            comp.setdefault(sc.foothold_node, 2.0)
        for i, pe in enumerate(self.phys_entries):
            if u_phys[i] < pe.probability:
                node = ig.node(pe.node_id)
                if node.zone == Zone.PHYSICAL:
                    failed[pe.node_id] = (0.0, "sabotage")
                    if pe.release and node.node_type in RELEASE_TYPES:
                        release.add(pe.node_id)
                else:
                    comp[pe.node_id] = 0.0
        entry_caps = {nid: set(caps) for nid, caps in sc.entry_nodes}
        resolved: dict = {}      # edge id -> (success, k)

        for _ in range(40):
            cap_time: dict = {}
            for nid, t in comp.items():
                for c in (caps_for(ig.node(nid)) | entry_caps.get(nid, set())):
                    if c not in cap_time or t < cap_time[c]:
                        cap_time[c] = t
            changed = False
            for u in list(comp.keys()):
                src = ig.node(u)
                for e in self.out[u]:
                    t_ready, ok = comp[u], True
                    for cnd in e.access_conditions:
                        sat, rt, _ = condition_status(cnd, src, self.env, cap_time)
                        if not sat:
                            ok = False
                            break
                        t_ready = max(t_ready, rt)
                    if not ok:
                        continue
                    tgt = ig.node(e.target)
                    if tgt.zone == Zone.PHYSICAL and e.edge_type == EdgeType.CONTROL:
                        pass
                    elif not zone_ok(e.target):
                        continue
                    ei = self.edge_index[e.id]
                    p = e.traversal_probability * (prob_scale.get(e.id, 1.0) if prob_scale else 1.0)
                    p = min(max(p, 1e-9), 1.0)
                    pt = self.p_total(p, K)
                    if u_edge[ei] >= pt:
                        continue
                    k = self.attempt_index(u_edge[ei], p)
                    t_end = t_ready + k
                    if e.id in isolated and t_end > tau:
                        continue          # isolation takes effect before the transition completes
                    if tgt.zone == Zone.PHYSICAL and e.edge_type == EdgeType.CONTROL:
                        if e.target not in failed or t_end < failed[e.target][0]:
                            failed[e.target] = (t_end, "actuation")
                            changed = True
                    elif e.target not in comp or t_end < comp[e.target]:
                        comp[e.target] = t_end
                        changed = True
                    resolved[e.id] = (t_ready, t_end)
            if not changed:
                break

        for e_id, (t0, t1) in resolved.items():
            out.used_edges.append((e_id, t0, t1))

        for nid, t in comp.items():
            node = ig.node(nid)
            if node.zone in sc.ransomware_zones and u_ransom[self.node_index[nid]] < sc.ransomware_prob:
                failed[nid] = (t + 1.0, "ransomware")
        out.compromised, out.failed, out.release = comp, failed, frozenset(release)
        return out
