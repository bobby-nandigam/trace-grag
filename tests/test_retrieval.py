"""Tests for retrieval strategies and localization scoring."""
import os

import pytest

from trace_grag.evaluation.localization import GoldLocation, gold_symbol_ids, parse_patch
from trace_grag.evaluation.metrics import mrr, recall_at_k, score_ranking
from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.parsing.python_parser import PythonParser
from trace_grag.retrieval.base import tokenize
from trace_grag.retrieval.graph_retrieval import GraphRetriever
from trace_grag.retrieval.lexical import BM25Retriever

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "minirepo")


@pytest.fixture(scope="module")
def graph():
    nodes, edges = PythonParser(FIXTURE, repo_name="minirepo").parse()
    g = RepoGraph(repo="minirepo")
    g.add_nodes(nodes)
    g.add_edges(edges)
    return g


def test_tokenize_splits_identifiers():
    assert tokenize("separability_matrix CompoundModel") == [
        "separability", "matrix", "compound", "model"]


def test_bm25_finds_divide_for_division_issue(graph):
    r = BM25Retriever()
    ranked = r.rank("divide raises error on zero division", graph)
    ids = [i for i, _ in ranked]
    div = graph.find_by_name("divide")[0].id
    assert div in ids[:3]


def test_graph_retriever_returns_targets_only(graph):
    r = GraphRetriever()
    ranked = r.rank("division by zero in calculator", graph)
    from trace_grag.retrieval.base import TARGET_TYPES
    for nid, _s in ranked:
        assert graph.node(nid).type in TARGET_TYPES


def test_metrics_basic():
    gold = {"a", "b"}
    ranked = ["x", "a", "y", "b"]
    assert recall_at_k(ranked, gold, 2) == 0.5
    assert mrr(ranked, gold) == pytest.approx(0.5)
    sc = score_ranking(ranked, gold, ks=(1, 2, 5))
    assert sc["hit@1"] == 0.0 and sc["hit@2"] == 1.0 and sc["recall@5"] == 1.0


def test_parse_patch_minus_side_ranges():
    patch = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n"
        "@@ -10,3 +10,4 @@ def foo():\n ctx\n-old\n+new\n+added\n"
        "diff --git a/tests/test_mod.py b/tests/test_mod.py\n"
        "--- a/tests/test_mod.py\n+++ b/tests/test_mod.py\n"
        "@@ -1,2 +1,3 @@\n+t\n"
    )
    gold = parse_patch(patch)
    assert gold.files == ["pkg/mod.py"]  # test file excluded
    assert gold.line_ranges["pkg/mod.py"] == [(10, 12)]


def test_gold_symbol_mapping(graph):
    # lines inside calc/core.py divide() should map to the divide node
    div = graph.find_by_name("divide")[0]
    gold = GoldLocation(files=["calc/core.py"],
                        line_ranges={"calc/core.py": [(div.start_line, div.start_line)]})
    ids = gold_symbol_ids(gold, graph)
    assert div.id in ids
