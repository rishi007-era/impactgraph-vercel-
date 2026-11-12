"""Operational criticality, downstream consequence and structural indicators.

Centrality is a SUPPLEMENTARY structural indicator. It never replaces operational criticality.
"""
from __future__ import annotations

import networkx as nx

from ..infrastructure.enums import EdgeType
from ..infrastructure.graph_builder import InfrastructureGraph

CONSEQUENCE_EDGES = {EdgeType.SERVICE_DEP, EdgeType.OPERATIONAL_DEP, EdgeType.PHYSICAL_FLOW, EdgeType.CONTROL}


def downstream_share(ig: InfrastructureGraph) -> dict:
    """D_i = importance of components that depend on, are controlled by, or are fed by i, as a share of total."""
    G = nx.DiGraph()
    G.add_nodes_from(n.id for n in ig.nodes)
    for e in ig.edges_by_type(*CONSEQUENCE_EDGES):
        G.add_edge(e.source, e.target)
    total = sum(n.operational_importance for n in ig.nodes)
    out = {}
    for n in ig.nodes:
        desc = nx.descendants(G, n.id)
        out[n.id] = min(1.0, sum(ig.node(d).operational_importance for d in desc) / total)
    return out


def betweenness(ig: InfrastructureGraph) -> dict:
    return nx.betweenness_centrality(nx.DiGraph(ig.attack_graph()))


def single_points_of_failure(ig: InfrastructureGraph, model) -> list:
    """Components whose individual failure drives delivered throughput to (almost) zero."""
    out = []
    for n in ig.nodes:
        c = model.evaluate(frozenset({n.id}))
        if c.throughput_fraction < 0.05:
            out.append(n.id)
    return out
