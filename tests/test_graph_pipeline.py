"""Tests for Stage 1-2: ingestion, parsing, and graph construction."""
import os

import pytest

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.graph.schema import CodeNode, EdgeType, NodeType, Provenance
from trace_grag.parsing.python_parser import PythonParser

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "minirepo")


@pytest.fixture(scope="module")
def graph():
    nodes, edges = PythonParser(FIXTURE, repo_name="minirepo").parse()
    g = RepoGraph(repo="minirepo")
    g.add_nodes(nodes)
    g.add_edges(edges)
    return g


def test_all_node_types_present(graph):
    by = graph.stats()["nodes_by_type"]
    for t in (NodeType.FILE, NodeType.MODULE, NodeType.CLASS,
              NodeType.FUNCTION, NodeType.METHOD, NodeType.TEST):
        assert by.get(t.value, 0) > 0, f"missing node type {t}"


def test_expected_edge_types(graph):
    by = graph.stats()["edges_by_type"]
    for t in (EdgeType.CONTAINS, EdgeType.DEFINES, EdgeType.CALLS,
              EdgeType.IMPORTS, EdgeType.TESTS):
        assert by.get(t.value, 0) > 0, f"missing edge type {t}"


def test_divide_is_a_function_with_location(graph):
    hits = graph.find_by_name("divide")
    assert len(hits) == 1
    n = hits[0]
    assert n.type == NodeType.FUNCTION
    assert n.qualified_name == "calc.core.divide"
    assert n.start_line > 0 and n.end_line >= n.start_line
    assert n.source_hash  # provenance: content hash recorded


def test_test_links_to_code_under_test(graph):
    # test_divide --TESTS--> calc.core.divide by naming convention
    tests_edges = [(u, v, d) for u, v, k, d in graph.graph.edges(keys=True, data=True)
                   if k == EdgeType.TESTS.value]
    linked = {(graph.node(u).name, graph.node(v).qualified_name)
              for u, v, d in tests_edges if graph.node(v)}
    assert ("test_divide", "calc.core.divide") in linked


def test_unresolved_calls_marked_not_invented(graph):
    # Every CALLS edge is either resolved to a real node or explicitly UNRESOLVED.
    for u, v, k, d in graph.graph.edges(keys=True, data=True):
        if k == EdgeType.CALLS.value:
            if d["provenance"] == Provenance.UNRESOLVED.value:
                assert d["dst"] == "" and d["raw_target"]
            else:
                assert graph.node(d["dst"]) is not None


def test_confidence_reflects_provenance(graph):
    for _u, _v, _k, d in graph.graph.edges(keys=True, data=True):
        if d["provenance"] == Provenance.NAME_HEURISTIC.value:
            assert d["confidence"] < 0.8  # heuristics are not trusted as facts


def test_neighbors_connect_test_caller_module(graph):
    did = graph.find_by_name("divide")[0].id
    neigh = {graph.node(n).qualified_name for n in graph.neighbors(did, depth=1)}
    assert "tests.test_core.test_divide" in neigh  # its test
    assert "calc.core.Calculator.run" in neigh      # its caller
    assert "calc.core" in neigh                       # its module


def test_persistence_roundtrip(graph, tmp_path):
    p = str(tmp_path / "g.json")
    graph.save(p)
    g2 = RepoGraph.load(p)
    assert g2.stats() == graph.stats()


def test_node_id_is_stable_and_unique(graph):
    ids = [n.id for n in graph._nodes.values()]
    assert len(ids) == len(set(ids))
    n = graph.find_by_name("divide")[0]
    assert n.id == CodeNode.make_id("minirepo", n.file_path, n.qualified_name, n.start_line)
