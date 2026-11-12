"""
Bug-localization ground truth from a gold patch.

The SWE-bench gold ``patch`` tells us exactly which source lines the human fix
touched. Because TRACE-GRAG builds its graph on the *base commit* (pre-fix), we
read the **old-file (minus) side** line ranges from each hunk header
``@@ -old_start,old_len +new_start,new_len @@`` — those index the base-commit
source that retrieval must surface.

This module is evaluator-only: the gold patch is never shown to the agent. It is
used *after* a run to score Recall@k / MRR against the ranked retrieval output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# test files are excluded from localization ground truth: the agent is scored on
# finding the *implementation* to fix, not the hidden tests.
_TEST_PATH = re.compile(r"(^|/)tests?/|(^|/)test_|_test\.py$|/conftest\.py$")


@dataclass
class GoldLocation:
    files: list[str] = field(default_factory=list)          # changed non-test files
    line_ranges: dict[str, list[tuple[int, int]]] = field(default_factory=dict)  # file -> base-commit ranges


def is_test_path(path: str) -> bool:
    return bool(_TEST_PATH.search(path))


def parse_patch(patch_text: str, include_tests: bool = False) -> GoldLocation:
    """Parse a unified diff into changed files and base-commit line ranges."""
    gold = GoldLocation()
    cur_file: str | None = None
    for line in patch_text.splitlines():
        if line.startswith("diff --git"):
            cur_file = None
        elif line.startswith("--- "):
            pass
        elif line.startswith("+++ "):
            # "+++ b/path/to/file.py"  (or /dev/null for deletions)
            target = line[4:].strip()
            target = target[2:] if target.startswith(("a/", "b/")) else target
            cur_file = None if target == "/dev/null" else target
        elif line.startswith("@@") and cur_file:
            m = _HUNK.match(line)
            if not m:
                continue
            if is_test_path(cur_file) and not include_tests:
                continue
            old_start = int(m.group(1))
            old_len = int(m.group(2) or "1")
            if cur_file not in gold.line_ranges:
                gold.files.append(cur_file)
                gold.line_ranges[cur_file] = []
            if old_len == 0:  # pure insertion: localize to the line it follows
                gold.line_ranges[cur_file].append((old_start, old_start + 1))
            else:
                gold.line_ranges[cur_file].append((old_start, old_start + old_len - 1))
    return gold


def gold_symbol_ids(gold: GoldLocation, graph) -> set[str]:
    """Map gold line ranges to the CodeNode ids that overlap them.

    A node is gold if it is a FUNCTION/METHOD/CLASS in a changed file whose
    [start_line, end_line] span intersects any gold range (the smallest such
    enclosing symbol is preferred, but all overlaps are returned for Recall).
    """
    from trace_grag.graph.schema import NodeType

    wanted = {NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS}
    out: set[str] = set()
    for n in graph._nodes.values():
        if n.type not in wanted or n.file_path not in gold.line_ranges:
            continue
        for (lo, hi) in gold.line_ranges[n.file_path]:
            if n.start_line <= hi and n.end_line >= lo:
                out.add(n.id)
                break
    return out
