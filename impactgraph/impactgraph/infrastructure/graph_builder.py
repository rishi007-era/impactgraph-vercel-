"""Typed, directed infrastructure graph (NetworkX MultiDiGraph wrapper).

The wrapper keeps the raw node/edge lists so the validator can report problems
(duplicate ids, dangling references) that a built graph would silently hide.
"""
from __future__ import annotations

import copy
import json
from typing import Iterable

import networkx as nx

from .edges import Edge
from .enums import ATTACK_TRAVERSABLE, DEPENDENCY_TYPES, EdgeType, Zone
from .nodes import Node


class InfrastructureGraph:
    def __init__(self, name: str, nodes: Iterable[Node], edges: Iterable[Edge]):
        self.name = name
        self.nodes: list = list(nodes)
        self.edges: list = list(edges)
        self._rebuild()

    # ---- construction -------------------------------------------------
    def _rebuild(self) -> None:
        self._node_index: dict = {}
        for n in self.nodes:
            self._node_index.setdefault(n.id, n)
        self._edge_index: dict = {}
        for e in self.edges:
            self._edge_index.setdefault(e.id, e)
        g = nx.MultiDiGraph(name=self.name)
        for n in self._node_index.values():
            g.add_node(n.id, data=n)
        for e in self._edge_index.values():
            if e.source in self._node_index and e.target in self._node_index:
                g.add_edge(e.source, e.target, key=e.id, data=e)
        self.g = g

    # ---- lookups ------------------------------------------------------
    def node(self, node_id: str) -> Node:
        return self._node_index[node_id]

    def edge(self, edge_id: str) -> Edge:
        return self._edge_index[edge_id]

    def zone_counts(self) -> dict:
        counts = {z: 0 for z in Zone}
        for n in self._node_index.values():
            counts[n.zone] += 1
        return counts

    def nodes_by_zone(self, zone: Zone) -> list:
        return [n for n in self._node_index.values() if n.zone == zone]

    def edges_by_type(self, *types: EdgeType) -> list:
        wanted = set(types)
        return [e for e in self._edge_index.values() if e.edge_type in wanted]

    def crosses_boundary(self, edge: Edge) -> bool:
        return self.node(edge.source).zone != self.node(edge.target).zone

    # ---- typed views (never mix relationship semantics) ---------------
    def subgraph_by_types(self, types: Iterable[EdgeType]) -> nx.MultiDiGraph:
        wanted = set(types)
        sub = nx.MultiDiGraph(name=f"{self.name}:{'+'.join(sorted(t.value for t in wanted))}")
        for nid, attrs in self.g.nodes(data=True):
            sub.add_node(nid, **attrs)
        for u, v, k, attrs in self.g.edges(keys=True, data=True):
            if attrs["data"].edge_type in wanted:
                sub.add_edge(u, v, key=k, **attrs)
        return sub

    def attack_graph(self) -> nx.MultiDiGraph:
        """Edges an adversary may traverse (network, auth, control). Never physical flow."""
        return self.subgraph_by_types(ATTACK_TRAVERSABLE)

    def dependency_graph(self) -> nx.MultiDiGraph:
        """Edges along which a failure can transfer (service and operational dependencies)."""
        return self.subgraph_by_types(DEPENDENCY_TYPES)

    def flow_graph(self) -> nx.MultiDiGraph:
        """Physical product-flow edges only."""
        return self.subgraph_by_types({EdgeType.PHYSICAL_FLOW})

    def dependencies_of(self, node_id: str) -> list:
        """Dependency edges whose target is this node (what it needs)."""
        return [e for _, _, e in self._in_edges(node_id) if e.is_dependency]

    def dependents_of(self, node_id: str) -> list:
        """Dependency edges whose source is this node (what needs it)."""
        return [e for _, _, e in self._out_edges(node_id) if e.is_dependency]

    def _in_edges(self, node_id):
        return [(u, v, d["data"]) for u, v, _, d in self.g.in_edges(node_id, keys=True, data=True)]

    def _out_edges(self, node_id):
        return [(u, v, d["data"]) for u, v, _, d in self.g.out_edges(node_id, keys=True, data=True)]

    # ---- persistence --------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InfrastructureGraph":
        return cls(d["name"], [Node.from_dict(n) for n in d["nodes"]], [Edge.from_dict(e) for e in d["edges"]])

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "InfrastructureGraph":
        return cls.from_dict(json.loads(text))

    def copy(self) -> "InfrastructureGraph":
        return InfrastructureGraph(self.name, copy.deepcopy(self.nodes), copy.deepcopy(self.edges))

    def summary(self) -> dict:
        by_type = {t.value: len(self.edges_by_type(t)) for t in EdgeType}
        return {
            "name": self.name,
            "nodes": len(self._node_index),
            "edges": len(self._edge_index),
            "zones": {z.value: c for z, c in self.zone_counts().items()},
            "edges_by_type": by_type,
        }
