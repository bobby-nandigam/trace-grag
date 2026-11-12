"""BM25 lexical retrieval (E1 baseline)."""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.retrieval.base import candidate_nodes, node_document, tokenize


class BM25Retriever:
    name = "bm25"

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._ids: list[str] = []

    def index(self, graph: RepoGraph) -> None:
        cands = candidate_nodes(graph)
        self._ids = [n.id for n in cands]
        corpus = [tokenize(node_document(n)) for n in cands]
        # BM25Okapi requires a non-empty corpus; guard tiny repos.
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def rank(self, issue: str, graph: RepoGraph) -> list[tuple[str, float]]:
        if self._bm25 is None or not self._ids:
            self.index(graph)
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(issue))
        ranked = sorted(zip(self._ids, scores), key=lambda x: x[1], reverse=True)
        return [(i, float(s)) for i, s in ranked]
