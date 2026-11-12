#!/usr/bin/env python
"""
Run the bug-localization tier (Tier A) over the benchmark manifest.

For each task: fetch a disk-safe snapshot at the base commit, build the repo
graph, derive gold symbol ids from the gold patch, run each retrieval strategy,
score Recall/hit/MRR, log per-task results, then delete the snapshot.

Usage:
  python scripts/run_localization.py                 # all tasks
  python scripts/run_localization.py --repos psf/requests pallets/flask
  python scripts/run_localization.py --limit 2 --keep-graph
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trace_grag.evaluation.localization import gold_symbol_ids  # noqa: E402
from trace_grag.evaluation.localization import GoldLocation  # noqa: E402
from trace_grag.evaluation.metrics import score_ranking  # noqa: E402
from trace_grag.graph.repo_graph import RepoGraph  # noqa: E402
from trace_grag.ingestion.snapshot import cleanup, fetch_snapshot  # noqa: E402
from trace_grag.parsing.python_parser import PythonParser  # noqa: E402
from trace_grag.retrieval.graph_retrieval import GraphRetriever  # noqa: E402
from trace_grag.retrieval.lexical import BM25Retriever  # noqa: E402
from trace_grag.retrieval.semantic import SemanticRetriever  # noqa: E402

MANIFEST = ROOT / "data" / "benchmark_manifest.jsonl"
SNAP_DIR = ROOT / ".snapshots" / "current"
OUT_DIR = ROOT / "results" / "localization"


def load_manifest() -> list[dict]:
    return [json.loads(l) for l in open(MANIFEST)]


def build_retrievers(use_semantic: bool = False) -> list:
    # E1 (BM25) and E3 (graph) are dependency-free and always run. E2 (semantic)
    # is opt-in because it needs a local Ollama embedding backend; keeping it off
    # by default means the harness stays reproducible without a running daemon.
    retrievers = [BM25Retriever(), GraphRetriever()]
    if use_semantic:
        retrievers.append(SemanticRetriever())  # E2 — default OllamaEmbedder
    return retrievers


def run_task(task: dict, keep_graph: bool, use_semantic: bool = False) -> dict:
    t0 = time.time()
    root = fetch_snapshot(task["repo"], task["base_commit"], str(SNAP_DIR))
    nodes, edges = PythonParser(str(root), repo_name=task["repo"].replace("/", "__")).parse()
    g = RepoGraph(repo=task["repo"]); g.add_nodes(nodes); g.add_edges(edges)
    build_s = time.time() - t0

    gold = GoldLocation(files=task["gold_files"],
                        line_ranges={f: [tuple(r) for r in rs]
                                     for f, rs in task["gold_line_ranges"].items()})
    gold_ids = gold_symbol_ids(gold, g)

    result = {
        "task_id": task["task_id"], "repo": task["repo"], "split": task["split"],
        "graph": g.stats(), "build_s": round(build_s, 2),
        "n_gold_symbols": len(gold_ids),
        "gold_files_present": [f for f in task["gold_files"]
                               if any(n.file_path == f for n in g._nodes.values())],
        "strategies": {},
    }
    if keep_graph:
        g.save(str(OUT_DIR / "graphs" / f"{task['task_id']}.json"))

    for r in build_retrievers(use_semantic):
        ts = time.time()
        try:
            ranked = r.rank(task["problem_statement"], g)
        except Exception as e:  # noqa: BLE001 - isolate per-strategy failure
            # One strategy failing (e.g. the embedding backend 500ing) must NOT
            # discard the other strategies' results for this task.
            result.setdefault("strategy_errors", {})[r.name] = repr(e)
            continue
        latency = time.time() - ts
        ranked_ids = [nid for nid, _s in ranked]
        sc = score_ranking(ranked_ids, gold_ids)
        sc["latency_s"] = round(latency, 3)
        sc["n_ranked"] = len(ranked_ids)
        result["strategies"][r.name] = sc

    cleanup(str(SNAP_DIR))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="*", help="only these repos")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--split", choices=["dev", "eval", "all"], default="all")
    ap.add_argument("--keep-graph", action="store_true")
    ap.add_argument("--semantic", action="store_true",
                    help="also run E2 dense retrieval (requires a local Ollama)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    tasks = load_manifest()
    if args.repos:
        tasks = [t for t in tasks if t["repo"] in set(args.repos)]
    if args.split != "all":
        tasks = [t for t in tasks if t["split"] == args.split]
    if args.limit:
        tasks = tasks[: args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"run-{stamp}.jsonl"
    print(f"running {len(tasks)} tasks -> {out_path}\n")

    with open(out_path, "w") as f:
        for i, task in enumerate(tasks, 1):
            try:
                res = run_task(task, args.keep_graph, args.semantic)
            except Exception as e:  # noqa: BLE001 - log failure, never silently drop
                res = {"task_id": task["task_id"], "repo": task["repo"],
                       "split": task["split"], "error": repr(e)}
                print(f"[{i}/{len(tasks)}] {task['task_id']}: ERROR {e!r}")
            else:
                parts = " | ".join(
                    f"{name} hit@10={sc['hit@10']:.0f} mrr={sc['mrr']:.2f}"
                    for name, sc in res["strategies"].items())
                print(f"[{i}/{len(tasks)}] {task['task_id']:30s} "
                      f"nodes={res['graph']['nodes']:5d} gold={res['n_gold_symbols']} | {parts}")
            f.write(json.dumps(res) + "\n")
            f.flush()
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
