"""Tests for E2 semantic retrieval (offline-deterministic + optional live smoke)."""
import hashlib
import os
import urllib.request

import numpy as np
import pytest

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.parsing.python_parser import PythonParser
from trace_grag.retrieval.base import TARGET_TYPES, tokenize
from trace_grag.retrieval.semantic import (
    EmbeddingError,
    OllamaEmbedder,
    SemanticRetriever,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "minirepo")
_DIM = 256


def _hash_embed(texts):
    """Deterministic bag-of-tokens hashing embedder — overlapping tokens raise
    cosine similarity, so it is meaningful for ranking without any network call."""
    out = []
    for t in texts:
        v = np.zeros(_DIM, dtype=np.float64)
        for tok in tokenize(t):
            # stable (process-independent) hash so the test is never seed-flaky
            h = int.from_bytes(hashlib.sha1(tok.encode()).digest()[:4], "big")
            v[h % _DIM] += 1.0
        out.append(v.tolist())
    return out


@pytest.fixture(scope="module")
def graph():
    nodes, edges = PythonParser(FIXTURE, repo_name="minirepo").parse()
    g = RepoGraph(repo="minirepo")
    g.add_nodes(nodes)
    g.add_edges(edges)
    return g


def test_semantic_ranks_divide_for_division_issue(graph):
    r = SemanticRetriever(embedder=_hash_embed)
    ranked = r.rank("divide raises error on zero division", graph)
    ids = [i for i, _ in ranked]
    div = graph.find_by_name("divide")[0].id
    assert div in ids[:3]


def test_semantic_returns_targets_only(graph):
    r = SemanticRetriever(embedder=_hash_embed)
    ranked = r.rank("division by zero", graph)
    for nid, _s in ranked:
        assert graph.node(nid).type in TARGET_TYPES


def test_semantic_scores_are_cosine_bounded(graph):
    r = SemanticRetriever(embedder=_hash_embed)
    ranked = r.rank("divide", graph)
    assert ranked, "expected non-empty ranking"
    for _nid, s in ranked:
        assert -1.0001 <= s <= 1.0001


def test_semantic_cache_avoids_recompute(graph):
    calls = {"n": 0}

    def counting(texts):
        calls["n"] += len(texts)
        return _hash_embed(texts)

    r = SemanticRetriever(embedder=counting)
    r.index(graph)
    after_first = calls["n"]
    r.index(graph)  # second index: all symbols unchanged -> served from cache
    assert calls["n"] == after_first, "unchanged symbols should not be re-embedded"


def test_empty_graph_ranks_empty():
    r = SemanticRetriever(embedder=_hash_embed)
    g = RepoGraph(repo="empty")
    assert r.rank("anything", g) == []


def test_ollama_embedder_errors_clearly_when_down():
    # Point at a closed port so the connection fails fast and surfaces EmbeddingError.
    emb = OllamaEmbedder(base_url="http://localhost:1", timeout=2, max_retries=1)
    with pytest.raises(EmbeddingError):
        emb(["hello"])


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_live_ollama_smoke(graph):
    """Live smoke test — only runs if a local Ollama is reachable."""
    r = SemanticRetriever(embedder=OllamaEmbedder())
    ranked = r.rank("divide raises error on zero division", graph)
    assert ranked
    ids = [i for i, _ in ranked]
    assert graph.find_by_name("divide")[0].id in ids[:5]
