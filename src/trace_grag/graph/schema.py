"""
TRACE-GRAG graph schema.

Typed node and edge definitions for the repository code graph. Unlike GRAG's
knowledge graph (which stores natural-language ``(subject, predicate, object)``
triples mined from prose), TRACE-GRAG nodes are *code symbols* with precise
source locations and provenance, and edges are *static-analysis relationships*
between them.

Design rules (from the project spec):
  * Every node carries a stable unique id, source location, and a content hash.
  * Every edge carries a relationship type, provenance (how it was derived),
    a confidence in [0, 1], and an optional source location.
  * We never fabricate a relationship static analysis cannot resolve; unresolved
    calls are recorded as unresolved rather than invented.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    FILE = "FILE"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    TEST = "TEST"


class EdgeType(str, Enum):
    CONTAINS = "CONTAINS"      # file/module -> symbol it textually contains
    DEFINES = "DEFINES"        # module/class -> symbol it defines (scope owner)
    IMPORTS = "IMPORTS"        # module -> module/symbol it imports
    CALLS = "CALLS"            # function/method -> callee it invokes
    TESTS = "TESTS"            # test -> symbol it exercises (static association)
    COVERS = "COVERS"          # test -> symbol executed under it (dynamic coverage)


class Provenance(str, Enum):
    """How an edge was derived — kept explicit so we never overstate certainty."""
    AST_STATIC = "ast_static"          # resolved from the syntax tree
    IMPORT_RESOLVED = "import_resolved"  # import resolved to a known module
    NAME_HEURISTIC = "name_heuristic"    # e.g. test_foo -> foo by naming convention
    CALL_RESOLVED = "call_resolved"      # callee resolved to a defined symbol
    COVERAGE_DYNAMIC = "coverage_dynamic"  # observed from a coverage run
    UNRESOLVED = "unresolved"            # recorded but target not resolvable


class CodeNode(BaseModel):
    """A single code symbol in the repository graph."""
    id: str                       # stable unique id, e.g. "repo::path::Class.method::L10"
    type: NodeType
    repo: str
    file_path: str                # repo-relative path
    name: str                     # symbol name (bare), "" for FILE nodes
    qualified_name: str = ""      # dotted path, e.g. "pkg.mod.Class.method"
    start_line: int = 0
    end_line: int = 0
    language: str = "python"
    source_hash: str = ""         # hash of the symbol's source text
    docstring: str = ""
    signature: str = ""           # def/class header line, for FUNCTION/METHOD/CLASS

    @staticmethod
    def make_id(repo: str, file_path: str, qualified_name: str, start_line: int) -> str:
        return f"{repo}::{file_path}::{qualified_name or '<module>'}::L{start_line}"

    @staticmethod
    def hash_source(source: str) -> str:
        return hashlib.sha1(source.encode("utf-8", "replace")).hexdigest()[:12]


class CodeEdge(BaseModel):
    """A directed, typed relationship between two code symbols."""
    src: str                      # source node id
    dst: str                      # destination node id (may be a placeholder for unresolved)
    type: EdgeType
    provenance: Provenance
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    src_file: str = ""            # file the relationship was observed in
    src_line: int = 0             # line the relationship was observed at
    # For unresolved targets we keep the raw textual target (e.g. the called name)
    # so later passes (or the agent) can still use it without us inventing an edge.
    raw_target: str = ""


# Default confidences by provenance — static resolution is trusted; heuristics less so.
DEFAULT_CONFIDENCE: dict[Provenance, float] = {
    Provenance.AST_STATIC: 1.0,
    Provenance.IMPORT_RESOLVED: 0.95,
    Provenance.CALL_RESOLVED: 0.9,
    Provenance.NAME_HEURISTIC: 0.6,
    Provenance.COVERAGE_DYNAMIC: 0.98,
    Provenance.UNRESOLVED: 0.3,
}
