"""Static graph retrieval (E3): lexical seeds + graph propagation."""
from __future__ import annotations

from collections import deque

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.retrieval.base import TARGET_TYPES
from trace_grag.retrieval.lexical import BM25Retriever


def _adjacency(graph: RepoGraph) -> dict[str, set[str]]:
    """Undirected adjacency over real code nodes (placeholders excluded)."""
    adj: dict[str, set[str]] = {n: set() for n in graph._nodes}
    for u, v, _k in graph.graph.edges(keys=True):
        if u in adj and v in adj:
            adj[u].add(v)
            adj[v].add(u)
    return adj


def _bfs_dist(adj: dict[str, set[str]], source: str, max_hops: int) -> dict[str, int]:
    dist = {source: 0}
    q = deque([source])
    while q:
        cur = q.popleft()
        if dist[cur] >= max_hops:
            continue
        for nb in adj.get(cur, ()):
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                q.append(nb)
    return dist


class GraphRetriever:
    name = "graph"

    def __init__(self, max_hops: int = 2, decay: float = 0.5,
                 n_seeds: int = 10, lexical_mix: float = 0.3) -> None:
        self.max_hops = max_hops
        self.decay = decay
        self.n_seeds = n_seeds
        self.lexical_mix = lexical_mix  # how much of the node's own lexical score to keep
        self._bm25 = BM25Retriever()

    def rank(self, issue: str, graph: RepoGraph) -> list[tuple[str, float]]:
        lex = self._bm25.rank(issue, graph)
        if not lex:
            return []
        top = lex[0][1] or 1.0
        lex_norm = {nid: (s / top if top else 0.0) for nid, s in lex}
        seeds = [nid for nid, _s in lex[: self.n_seeds]]

        adj = _adjacency(graph)
        prop: dict[str, float] = {}
        for seed in seeds:
            sscore = lex_norm.get(seed, 0.0)
            if sscore <= 0:
                continue
            for node, d in _bfs_dist(adj, seed, self.max_hops).items():
                contrib = sscore * (self.decay ** d)
                if contrib > prop.get(node, 0.0):
                    prop[node] = contrib

        # Combine propagated structural score with the node's own lexical score,
        # then restrict to localization-target node types.
        targets = {n.id for n in graph._nodes.values() if n.type in TARGET_TYPES}
        combined: dict[str, float] = {}
        for nid in targets:
            combined[nid] = prop.get(nid, 0.0) + self.lexical_mix * lex_norm.get(nid, 0.0)
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in ranked if s > 0]
