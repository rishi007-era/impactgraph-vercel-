"""Infrastructure resilience metrics for a strategy outcome (Phase 1: steady-state, no recovery dynamics).

Phase 2 adds time-based degradation/recovery curves. Here we report what remains operational after an incident
and after the chosen containment, on the same Monte Carlo trials.
"""
from __future__ import annotations

import networkx as nx

from ..infrastructure.enums import Condition, EdgeType, Zone
from ..infrastructure.graph_builder import InfrastructureGraph


def operational_connectivity(ig: InfrastructureGraph, failed: set, isolated_edges) -> float:
    """Share of surviving components inside the largest connected group once failed components are removed
    and isolated links are cut (all relationship types, undirected)."""
    G = nx.Graph()
    G.add_nodes_from(n.id for n in ig.nodes if n.id not in failed)
    for e in ig.edges:
        if e.id in isolated_edges or e.source in failed or e.target in failed:
            continue
        G.add_edge(e.source, e.target)
    if G.number_of_nodes() == 0:
        return 0.0
    return max(len(c) for c in nx.connected_components(G)) / len(ig.nodes)


def summarize(ig, model, mc_result, isolated_edges) -> dict:
    """Resilience summary from a Monte Carlo result (means over trials)."""
    n = len(ig.nodes)
    delivery = [x.id for x in ig.nodes if x.node_type.value == "delivery_point"]
    operational = [1.0 - mc_result.freq_failed[i.id] for i in ig.nodes]
    return {
        "throughput_fraction": mc_result.mean("throughput"),
        "throughput_p05": float(sorted(mc_result.throughput)[int(0.05 * len(mc_result.throughput))]),
        "service_availability": 1.0 - mc_result.mean("service_loss"),
        "operational_components_share": float(sum(operational) / n),
        "delivery_points_served_share": mc_result.mean("throughput") if delivery else 0.0,
        "p_physical_failure": mc_result.mean("phys_hit"),
    }
