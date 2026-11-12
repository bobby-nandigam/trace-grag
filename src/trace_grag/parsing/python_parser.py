"""
Python repository parser (built-in ``ast`` backend).

Extracts code-graph nodes and edges from a Python repository. We use the standard
library ``ast`` module rather than Tree-sitter for the Python pipeline: it is
precise, version-matched, and dependency-free. Tree-sitter remains the documented
path for adding JavaScript/TypeScript later (see docs/ARCHITECTURE.md).

Two passes:
  1. Collect every defined symbol (so calls/tests can be resolved to real nodes).
  2. Emit CONTAINS / DEFINES / IMPORTS / CALLS / TESTS edges, marking anything
     unresolved explicitly instead of inventing a target.
"""

from __future__ import annotations

import ast
import logging
import os
import warnings
from pathlib import Path
from typing import Optional

from trace_grag.graph.schema import (
    DEFAULT_CONFIDENCE,
    CodeEdge,
    CodeNode,
    EdgeType,
    NodeType,
    Provenance,
)

logger = logging.getLogger(__name__)

# Directories we never index (generated / vendored / noise).
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", "build", "dist", ".eggs", "site-packages",
    ".idea", ".vscode", "migrations",
}


def _is_test_file(path: str) -> bool:
    b = os.path.basename(path)
    return b.startswith("test_") or b.endswith("_test.py") or "/tests/" in path.replace(os.sep, "/")


def _is_test_name(name: str) -> bool:
    return name.startswith("test") or name.startswith("Test")


def _module_name(repo_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(repo_root).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(parts)


class PythonParser:
    def __init__(self, repo_root: str, repo_name: Optional[str] = None):
        self.repo_root = Path(repo_root).resolve()
        self.repo = repo_name or self.repo_root.name
        self.nodes: list[CodeNode] = []
        self.edges: list[CodeEdge] = []
        # qualified_name -> node id and bare name -> set[node id], for resolution
        self._by_qual: dict[str, str] = {}
        self._by_bare: dict[str, set[str]] = {}
        self._module_of_file: dict[str, str] = {}  # file_path -> module qualified name

    # ── public ────────────────────────────────────────────────────────────────
    def parse(self) -> tuple[list[CodeNode], list[CodeEdge]]:
        files = self._discover_files()
        trees: dict[str, tuple[ast.AST, str]] = {}
        # Pass 1: nodes + symbol table
        for fp in files:
            try:
                src = fp.read_text(encoding="utf-8", errors="replace")
                with warnings.catch_warnings():
                    # old benchmark code triggers SyntaxWarning (e.g. invalid
                    # escape sequences in docstrings) — noise, not parse failure.
                    warnings.simplefilter("ignore")
                    tree = ast.parse(src, filename=str(fp))
            except (SyntaxError, ValueError) as e:
                logger.warning("skip unparseable %s: %s", fp, e)
                continue
            trees[str(fp)] = (tree, src)
            self._emit_file_nodes(fp, tree, src)
        # Pass 2: edges that need the full symbol table
        for fp_str, (tree, src) in trees.items():
            self._emit_call_and_test_edges(Path(fp_str), tree, src)
        logger.info("parsed %s: %d nodes, %d edges", self.repo, len(self.nodes), len(self.edges))
        return self.nodes, self.edges

    # ── discovery ──────────────────────────────────────────────────────────────
    def _discover_files(self) -> list[Path]:
        out: list[Path] = []
        for root, dirs, names in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for n in names:
                if n.endswith(".py"):
                    out.append(Path(root) / n)
        return sorted(out)

    # ── pass 1 ──────────────────────────────────────────────────────────────────
    def _register(self, node: CodeNode) -> None:
        self.nodes.append(node)
        self._by_qual[node.qualified_name] = node.id
        self._by_bare.setdefault(node.name, set()).add(node.id)

    def _emit_file_nodes(self, fp: Path, tree: ast.AST, src: str) -> None:
        rel = str(fp.relative_to(self.repo_root))
        mod = _module_name(self.repo_root, fp)
        self._module_of_file[rel] = mod
        lines = src.splitlines()
        n_lines = len(lines)
        is_test_file = _is_test_file(rel)

        file_id = CodeNode.make_id(self.repo, rel, "<file>", 1)
        file_node = CodeNode(
            id=file_id, type=NodeType.FILE, repo=self.repo, file_path=rel,
            name=fp.name, qualified_name=mod, start_line=1, end_line=n_lines,
            source_hash=CodeNode.hash_source(src),
        )
        self.add_node_safe(file_node)
        # MODULE node (the importable unit) — distinct from the FILE on disk.
        mod_id = CodeNode.make_id(self.repo, rel, mod or rel, 1)
        mod_node = CodeNode(
            id=mod_id, type=NodeType.MODULE, repo=self.repo, file_path=rel,
            name=mod.split(".")[-1] if mod else fp.stem, qualified_name=mod,
            start_line=1, end_line=n_lines, source_hash=file_node.source_hash,
        )
        self._register(mod_node)
        self._edge(file_id, mod_id, EdgeType.CONTAINS, Provenance.AST_STATIC, rel, 1)

        # imports
        for stmt in ast.walk(tree):
            if isinstance(stmt, ast.Import):
                for a in stmt.names:
                    self._emit_import(mod_id, a.name, rel, stmt.lineno)
            elif isinstance(stmt, ast.ImportFrom):
                base = ("." * (stmt.level or 0)) + (stmt.module or "")
                self._emit_import(mod_id, base, rel, stmt.lineno)

        # top-level defs
        self._walk_defs(tree, parent_id=mod_id, parent_qual=mod, rel=rel,
                        src_lines=lines, is_test_file=is_test_file, class_scope=False)

    def _walk_defs(self, scope: ast.AST, parent_id: str, parent_qual: str, rel: str,
                   src_lines: list[str], is_test_file: bool, class_scope: bool) -> None:
        for child in ast.iter_child_nodes(scope):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._emit_callable(child, parent_id, parent_qual, rel, src_lines,
                                    is_test_file, method=class_scope)
            elif isinstance(child, ast.ClassDef):
                self._emit_class(child, parent_id, parent_qual, rel, src_lines, is_test_file)

    def _emit_class(self, node: ast.ClassDef, parent_id: str, parent_qual: str,
                    rel: str, src_lines: list[str], is_test_file: bool) -> None:
        qual = f"{parent_qual}.{node.name}" if parent_qual else node.name
        start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
        src = "\n".join(src_lines[start - 1:end])
        cid = CodeNode.make_id(self.repo, rel, qual, start)
        is_test = is_test_file and node.name.startswith("Test")
        cnode = CodeNode(
            id=cid, type=NodeType.TEST if is_test else NodeType.CLASS, repo=self.repo,
            file_path=rel, name=node.name, qualified_name=qual, start_line=start,
            end_line=end, source_hash=CodeNode.hash_source(src),
            docstring=ast.get_docstring(node) or "",
            signature=src_lines[start - 1].strip() if start - 1 < len(src_lines) else "",
        )
        self._register(cnode)
        self._edge(parent_id, cid, EdgeType.DEFINES, Provenance.AST_STATIC, rel, start)
        # methods
        self._walk_defs(node, parent_id=cid, parent_qual=qual, rel=rel,
                        src_lines=src_lines, is_test_file=is_test_file, class_scope=True)

    def _emit_callable(self, node, parent_id: str, parent_qual: str, rel: str,
                       src_lines: list[str], is_test_file: bool, method: bool) -> None:
        qual = f"{parent_qual}.{node.name}" if parent_qual else node.name
        start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
        src = "\n".join(src_lines[start - 1:end])
        nid = CodeNode.make_id(self.repo, rel, qual, start)
        is_test = (is_test_file and node.name.startswith("test")) or node.name.startswith("test_")
        if is_test:
            ntype = NodeType.TEST
        elif method:
            ntype = NodeType.METHOD
        else:
            ntype = NodeType.FUNCTION
        fnode = CodeNode(
            id=nid, type=ntype, repo=self.repo, file_path=rel, name=node.name,
            qualified_name=qual, start_line=start, end_line=end,
            source_hash=CodeNode.hash_source(src),
            docstring=ast.get_docstring(node) or "",
            signature=src_lines[start - 1].strip() if start - 1 < len(src_lines) else "",
        )
        self._register(fnode)
        self._edge(parent_id, nid, EdgeType.DEFINES, Provenance.AST_STATIC, rel, start)

    def _emit_import(self, mod_id: str, target: str, rel: str, line: int) -> None:
        if not target:
            return
        # Resolve to an in-repo module if we know it; else record unresolved.
        dst = self._by_qual.get(target, "")
        prov = Provenance.IMPORT_RESOLVED if dst else Provenance.UNRESOLVED
        self._edge(mod_id, dst, EdgeType.IMPORTS, prov, rel, line, raw_target=target)

    # ── pass 2 ────────────────────────────────────────────────────────────────
    def _emit_call_and_test_edges(self, fp: Path, tree: ast.AST, src: str) -> None:
        rel = str(fp.relative_to(self.repo_root))
        # Build a map of (lineno) -> enclosing defined node id for this file.
        enclosing = self._enclosing_map(rel)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                callee = self._call_name(n.func)
                if not callee:
                    continue
                caller_id = self._nearest_enclosing(enclosing, n.lineno)
                if caller_id is None:
                    continue
                targets = self._by_bare.get(callee.split(".")[-1], set())
                if targets:
                    for t in targets:
                        self._edge(caller_id, t, EdgeType.CALLS, Provenance.CALL_RESOLVED,
                                   rel, n.lineno, raw_target=callee)
                else:
                    self._edge(caller_id, "", EdgeType.CALLS, Provenance.UNRESOLVED,
                               rel, n.lineno, raw_target=callee)
        # TESTS edges by naming convention: test_foo -> foo
        for node in self.nodes:
            if node.type == NodeType.TEST and node.file_path == rel:
                target = node.name[len("test_"):] if node.name.startswith("test_") else node.name[4:]
                target = target.strip("_")
                for t in self._by_bare.get(target, set()):
                    if self._nodes_at(t).type != NodeType.TEST:
                        self._edge(node.id, t, EdgeType.TESTS, Provenance.NAME_HEURISTIC,
                                   rel, node.start_line, raw_target=target)

    def _enclosing_map(self, rel: str) -> list[tuple[int, int, str]]:
        spans = [(n.start_line, n.end_line, n.id) for n in self.nodes
                 if n.file_path == rel and n.type in
                 {NodeType.FUNCTION, NodeType.METHOD, NodeType.TEST}]
        spans.sort(key=lambda s: (s[0], -(s[1])))
        return spans

    @staticmethod
    def _nearest_enclosing(spans, line: int) -> Optional[str]:
        best = None
        best_span = None
        for start, end, nid in spans:
            if start <= line <= end:
                span = end - start
                if best_span is None or span < best_span:
                    best, best_span = nid, span
        return best

    def _nodes_at(self, nid: str) -> CodeNode:
        return next(n for n in self.nodes if n.id == nid)

    @staticmethod
    def _call_name(func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return ""

    # ── helpers ──────────────────────────────────────────────────────────────
    def add_node_safe(self, node: CodeNode) -> None:
        self.nodes.append(node)

    def _edge(self, src: str, dst: str, etype: EdgeType, prov: Provenance,
              rel: str, line: int, raw_target: str = "") -> None:
        self.edges.append(CodeEdge(
            src=src, dst=dst, type=etype, provenance=prov,
            confidence=DEFAULT_CONFIDENCE[prov], src_file=rel, src_line=line,
            raw_target=raw_target,
        ))
