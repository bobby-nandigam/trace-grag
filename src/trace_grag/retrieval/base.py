"""Shared retrieval interface, tokenization, and candidate selection."""
from __future__ import annotations

import re
from typing import Protocol

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.graph.schema import CodeNode, NodeType

# Localization targets: the symbol kinds a patch can land in.
TARGET_TYPES = {NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS}

_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, splitting snake_case and CamelCase identifiers."""
    out: list[str] = []
    for raw in _SPLIT.split(text or ""):
        if not raw:
            continue
        for piece in _CAMEL.split(raw):
            p = piece.lower()
            if len(p) > 1:
                out.append(p)
    return out


def node_document(node: CodeNode) -> str:
    """The text used to represent a node for lexical/semantic retrieval."""
    parts = [node.qualified_name, node.name, node.signature, node.docstring]
    return " ".join(p for p in parts if p)


def candidate_nodes(graph: RepoGraph) -> list[CodeNode]:
    return [n for n in graph._nodes.values() if n.type in TARGET_TYPES]


class Retriever(Protocol):
    name: str

    def rank(self, issue: str, graph: RepoGraph) -> list[tuple[str, float]]:
        """Return (node_id, score) pairs, highest score first."""
        ...
