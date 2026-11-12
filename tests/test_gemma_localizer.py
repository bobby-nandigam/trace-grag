"""Offline tests for the Gemma localizer (fake chat backend — no model needed)."""
import os

import pytest

from trace_grag.agent.gemma_localizer import (
    ChatError,
    GemmaLocalizer,
    OllamaChat,
    build_prompt,
    parse_choice,
)
from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.parsing.python_parser import PythonParser
from trace_grag.retrieval.base import candidate_nodes

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "minirepo")


@pytest.fixture(scope="module")
def candidates():
    nodes, edges = PythonParser(FIXTURE, repo_name="minirepo").parse()
    g = RepoGraph("minirepo"); g.add_nodes(nodes); g.add_edges(edges)
    return candidate_nodes(g)


def test_parse_choice_extracts_valid_index():
    assert parse_choice("3", 10) == 3
    assert parse_choice("The answer is 2.", 10) == 2
    assert parse_choice("42", 10) is None   # out of range
    assert parse_choice("none", 10) is None  # unparseable -> abstention
    assert parse_choice("", 5) is None


def test_prompt_lists_candidates_and_issue(candidates):
    p = build_prompt("division by zero bug", candidates[:5])
    assert "division by zero" in p
    assert "1." in p and "2." in p
    assert p.rstrip().endswith("Number:")


def test_localize_picks_the_indicated_candidate(candidates):
    # Fake model always answers "2" -> must map to the 2nd candidate's id.
    loc = GemmaLocalizer(chat=lambda prompt: "2", top_k=10)
    cands = candidates[:10]
    out = loc.localize("some issue", cands)
    assert out["choice"] == 2
    assert out["chosen_id"] == cands[1].id
    assert out["n_candidates"] == len(cands)


def test_localize_abstains_on_unparseable(candidates):
    loc = GemmaLocalizer(chat=lambda prompt: "I am not sure", top_k=5)
    out = loc.localize("issue", candidates[:5])
    assert out["choice"] is None and out["chosen_id"] is None  # never guessed into a hit


def test_localize_empty_candidates():
    loc = GemmaLocalizer(chat=lambda prompt: "1")
    out = loc.localize("issue", [])
    assert out["chosen_id"] is None and out["n_candidates"] == 0


def test_ollama_chat_errors_clearly_when_down():
    chat = OllamaChat(base_url="http://localhost:1", timeout=2)
    with pytest.raises(ChatError):
        chat("hello")
