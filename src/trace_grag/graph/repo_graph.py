"""
RepoGraph — the repository code graph store.

Backed by a NetworkX ``MultiDiGraph`` (one parallel edge per relationship type),
mirroring the storage/persistence pattern proven in GRAG's ``KnowledgeGraph`` but
with a code-symbol schema instead of NL triples. Persistence uses a flat
node-list + edge-list JSON so it is independent of the installed NetworkX version.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import networkx as nx

from trace_grag.graph.schema import CodeEdge, CodeNode, EdgeType, NodeType

logger = logging.getLogger(__name__)


class RepoGraph:
    def __init__(self, repo: str = "repo"):
        self.repo = repo
        self.graph = nx.MultiDiGraph()
        self._nodes: dict[str, CodeNode] = {}
        # name -> set of node ids, for fast symbol lookup (bare + qualified names)
        self._name_index: dict[str, set[str]] = defaultdict(set)

    # ── construction ─────────────────────────────────────────────────────────
    def add_node(self, node: CodeNode) -> None:
        self._nodes[node.id] = node
        self.graph.add_node(node.id, **node.model_dump())
        if node.name:
            self._name_index[node.name].add(node.id)
        if node.qualified_name:
            self._name_index[node.qualified_name].add(node.id)

    def add_edge(self, edge: CodeEdge) -> None:
        # Keep edges whose dst is a real node, OR unresolved edges (dst == "")
        # so provenance of what could NOT be resolved is preserved too.
        self.graph.add_edge(
            edge.src, edge.dst or f"<unresolved:{edge.raw_target}>",
            key=edge.type.value,
            **edge.model_dump(),
        )

    def add_nodes(self, nodes: Iterable[CodeNode]) -> None:
        for n in nodes:
            self.add_node(n)

    def add_edges(self, edges: Iterable[CodeEdge]) -> None:
        for e in edges:
            self.add_edge(e)

    # ── lookup ───────────────────────────────────────────────────────────────
    def node(self, node_id: str) -> Optional[CodeNode]:
        return self._nodes.get(node_id)

    def find_by_name(self, name: str) -> list[CodeNode]:
        """Exact match on bare or qualified name."""
        return [self._nodes[i] for i in self._name_index.get(name, set()) if i in self._nodes]

    def search_symbols(self, query: str, limit: int = 20) -> list[CodeNode]:
        """Case-insensitive substring match over symbol names — the agent's
        ``search_symbols`` tool and a lexical retrieval fallback both use this."""
        q = query.lower()
        hits = [n for n in self._nodes.values() if q in n.name.lower() or q in n.qualified_name.lower()]
        hits.sort(key=lambda n: (len(n.name), n.qualified_name))
        return hits[:limit]

    def neighbors(self, node_id: str, depth: int = 1,
                  edge_types: Optional[set[EdgeType]] = None) -> set[str]:
        """Undirected k-hop neighborhood, optionally filtered to edge types."""
        if node_id not in self.graph:
            return set()
        wanted = {e.value for e in edge_types} if edge_types else None
        seen: set[str] = set()
        frontier = {node_id}
        for _ in range(depth):
            nxt: set[str] = set()
            for n in frontier:
                for _u, v, k in self.graph.out_edges(n, keys=True):
                    if wanted is None or k in wanted:
                        nxt.add(v)
                for u, _v, k in self.graph.in_edges(n, keys=True):
                    if wanted is None or k in wanted:
                        nxt.add(u)
            seen |= nxt
            frontier = nxt
        seen.discard(node_id)
        return {n for n in seen if not n.startswith("<unresolved:")}

    def connected_subgraph(self, seed_ids: Iterable[str], depth: int = 1) -> set[str]:
        """Node ids forming a connected neighborhood around the seeds — the
        structural basis for budget-aware context selection (Contribution 3)."""
        result: set[str] = set()
        for s in seed_ids:
            result.add(s)
            result |= self.neighbors(s, depth=depth)
        return {n for n in result if n in self._nodes}

    def edges_between(self, src: str, dst: str) -> list[CodeEdge]:
        out = []
        if self.graph.has_edge(src, dst):
            for data in self.graph[src][dst].values():
                out.append(CodeEdge(**{k: data[k] for k in CodeEdge.model_fields if k in data}))
        return out

    # ── stats / persistence ──────────────────────────────────────────────────
    def stats(self) -> dict:
        # Count only real code nodes by type; unresolved-target placeholders
        # (graph nodes created for edges whose dst could not be resolved) are
        # reported separately so the schema counts stay honest.
        by_type: dict[str, int] = defaultdict(int)
        for n in self._nodes.values():
            by_type[n.type.value] += 1
        by_edge: dict[str, int] = defaultdict(int)
        for _u, _v, k in self.graph.edges(keys=True):
            by_edge[k] += 1
        placeholders = self.graph.number_of_nodes() - len(self._nodes)
        return {
            "nodes": len(self._nodes),
            "edges": self.graph.number_of_edges(),
            "unresolved_targets": placeholders,
            "nodes_by_type": dict(by_type),
            "edges_by_type": dict(by_edge),
        }

    def save(self, path: str) -> None:
        nodes = [n.model_dump() for n in self._nodes.values()]
        edges = []
        for _u, _v, _k, data in self.graph.edges(keys=True, data=True):
            edges.append({k: data[k] for k in CodeEdge.model_fields if k in data})
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"repo": self.repo, "nodes": nodes, "edges": edges}, f)
        logger.info("RepoGraph saved to %s | %d nodes, %d edges", path, len(nodes), len(edges))

    @classmethod
    def load(cls, path: str) -> "RepoGraph":
        with open(path) as f:
            data = json.load(f)
        g = cls(repo=data.get("repo", "repo"))
        g.add_nodes(CodeNode(**n) for n in data["nodes"])
        g.add_edges(CodeEdge(**e) for e in data["edges"])
        return g
