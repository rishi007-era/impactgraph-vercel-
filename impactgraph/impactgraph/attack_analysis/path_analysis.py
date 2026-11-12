"""Attack-path analysis on the attack-traversable subgraph (never physical flow).

Method: weighted shortest simple paths with weight = -ln(p_total) where p_total = 1-(1-p)^attempts, then each
candidate path is checked SEQUENTIALLY: an edge counts as feasible only if its access conditions are satisfied by
environment flags, source properties, or capabilities gained earlier on the path. Every hop reports WHY it is feasible.
Probabilities are assumed model values, not calibrated.
"""
from __future__ import annotations

import math
from itertools import islice

import networkx as nx

from ..infrastructure.graph_builder import InfrastructureGraph
from ..simulation.scenarios import Scenario
from .access_rules import DEFAULT_ENV, caps_for, condition_status
from .attack_model import AttackModel


def _check_path(ig, sc, env, nodes, edges):
    entry_caps = {}
    for nid, caps in sc.entry_nodes:
        entry_caps[nid] = set(caps)
    caps_held = set(caps_for(ig.node(nodes[0]))) | entry_caps.get(nodes[0], set())
    hops, ok_all, cum = [], True, 1.0
    for i, e in enumerate(edges):
        cap_time = {c: 0.0 for c in caps_held}
        reasons, ok = [], True
        for c in e.access_conditions:
            sat, _, why = condition_status(c, ig.node(e.source), env, cap_time)
            reasons.append((c, sat, why))
            ok &= sat
        pt = AttackModel.p_total(e.traversal_probability, sc.attempts)
        crossing = ig.node(e.source).zone != ig.node(e.target).zone
        hops.append({"edge": e.id, "source": e.source, "target": e.target, "type": e.edge_type.value,
                     "p_single": e.traversal_probability, "p_total": pt, "feasible": ok, "conditions": reasons,
                     "crosses_boundary": crossing,
                     "zones": f"{ig.node(e.source).zone.value} -> {ig.node(e.target).zone.value}"})
        cum *= pt
        ok_all &= ok
        caps_held |= caps_for(ig.node(e.target))
    return ok_all, cum, hops


def top_paths(ig: InfrastructureGraph, sc: Scenario, source: str, target: str, k: int = 3, cutoff: int = 12):
    env = dict(DEFAULT_ENV); env.update(sc.env)
    ag = nx.DiGraph()
    ag.add_nodes_from(n.id for n in ig.nodes)
    best = {}
    for e in ig.edges:
        if not e.is_attack_traversable:
            continue
        w = -math.log(AttackModel.p_total(e.traversal_probability, sc.attempts))
        key = (e.source, e.target)
        if key not in best or w < best[key][0]:
            best[key] = (w, e)
    for (u, v), (w, e) in best.items():
        ag.add_edge(u, v, weight=w, edge=e)
    if source not in ag or target not in ag or not nx.has_path(ag, source, target):
        return []
    out = []
    for p in islice(nx.shortest_simple_paths(ag, source, target, weight="weight"), 200):
        if len(p) - 1 > cutoff:
            continue
        edges = [ag[u][v]["edge"] for u, v in zip(p, p[1:])]
        ok, cum, hops = _check_path(ig, sc, env, p, edges)
        if ok:
            out.append({"nodes": p, "probability": cum, "hops": hops, "length": len(edges),
                        "boundary_crossings": [h["edge"] for h in hops if h["crosses_boundary"]]})
        if len(out) >= k:
            break
    return out


def reachability(ig: InfrastructureGraph, sc: Scenario, source: str) -> dict:
    ag = ig.attack_graph()
    reach = nx.descendants(nx.DiGraph(ag), source) | {source}
    z = {}
    for n in reach:
        z.setdefault(ig.node(n).zone.value, []).append(n)
    return z
