#!/usr/bin/env python
"""
Gemma-in-the-loop localization: does better retrieval help Gemma 4 localize bugs?

For each task and each retriever (E1 BM25, E3 graph, optionally E2 semantic), we take
the retriever's top-K candidate symbols and ask the local Gemma 4 model to pick the
single symbol to fix. We score:

  * gemma_hit   — Gemma's pick is a gold symbol (the headline: model localization)
  * gold_in_topk — any gold symbol was in the top-K the model saw (the recall gate:
                   Gemma cannot pick what retrieval never surfaced)
  * retr_top1_hit — the retriever's own rank-1 is gold (retrieval-only baseline)

Usage:
  python scripts/run_gemma_localization.py --repos psf/requests pallets/flask --semantic
  python scripts/run_gemma_localization.py --limit 8 --top-k 10
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

from trace_grag.agent.gemma_localizer import GemmaLocalizer, OllamaChat  # noqa: E402
from trace_grag.evaluation.localization import GoldLocation, gold_symbol_ids  # noqa: E402
from trace_grag.graph.repo_graph import RepoGraph  # noqa: E402
from trace_grag.ingestion.snapshot import cleanup, fetch_snapshot  # noqa: E402
from trace_grag.parsing.python_parser import PythonParser  # noqa: E402
from trace_grag.retrieval.graph_retrieval import GraphRetriever  # noqa: E402
from trace_grag.retrieval.lexical import BM25Retriever  # noqa: E402
from trace_grag.retrieval.semantic import SemanticRetriever  # noqa: E402

MANIFEST = ROOT / "data" / "benchmark_manifest.jsonl"
SNAP_DIR = ROOT / ".snapshots" / "gemma"
OUT_DIR = ROOT / "results" / "gemma_localization"


def build_retrievers(use_semantic: bool):
    r = [("bm25", BM25Retriever()), ("graph", GraphRetriever())]
    if use_semantic:
        r.insert(1, ("semantic", SemanticRetriever()))
    return r


def run_task(task: dict, localizer: GemmaLocalizer, use_semantic: bool, top_k: int) -> dict:
    root = fetch_snapshot(task["repo"], task["base_commit"], str(SNAP_DIR))
    nodes, edges = PythonParser(str(root), repo_name=task["repo"].replace("/", "__")).parse()
    g = RepoGraph(repo=task["repo"]); g.add_nodes(nodes); g.add_edges(edges)
    gold = GoldLocation(files=task["gold_files"],
                        line_ranges={f: [tuple(r) for r in rs]
                                     for f, rs in task["gold_line_ranges"].items()})
    gold_ids = gold_symbol_ids(gold, g)

    res = {"task_id": task["task_id"], "repo": task["repo"], "split": task["split"],
           "n_gold": len(gold_ids), "strategies": {}}
    for name, r in build_retrievers(use_semantic):
        try:
            ranked = r.rank(task["problem_statement"], g)
            top_nodes = [g.node(nid) for nid, _ in ranked[:top_k] if g.node(nid)]
            gold_in_topk = any(n.id in gold_ids for n in top_nodes)
            retr_top1_hit = bool(top_nodes) and top_nodes[0].id in gold_ids
            pick = localizer.localize(task["problem_statement"], top_nodes)
            res["strategies"][name] = {
                "gemma_hit": int(pick["chosen_id"] in gold_ids) if pick["chosen_id"] else 0,
                "gold_in_topk": int(gold_in_topk),
                "retr_top1_hit": int(retr_top1_hit),
                "gemma_choice": pick["choice"],
                "abstained": int(pick["choice"] is None),
                "raw": pick["raw"],
            }
        except Exception as e:  # noqa: BLE001 - isolate per strategy
            res.setdefault("strategy_errors", {})[name] = repr(e)
    cleanup(str(SNAP_DIR))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--split", choices=["dev", "eval", "all"], default="all")
    ap.add_argument("--semantic", action="store_true")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--model", default="gemma4:e2b")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    tasks = [json.loads(l) for l in open(MANIFEST)]
    if args.repos:
        tasks = [t for t in tasks if t["repo"] in set(args.repos)]
    if args.split != "all":
        tasks = [t for t in tasks if t["split"] == args.split]
    if args.limit:
        tasks = tasks[: args.limit]

    localizer = GemmaLocalizer(chat=OllamaChat(model=args.model), top_k=args.top_k)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"gemma-{args.model.replace(':', '_')}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    print(f"model={args.model} top_k={args.top_k} | {len(tasks)} tasks -> {out_path}\n")

    agg: dict[str, dict[str, int]] = {}
    with open(out_path, "w") as f:
        for i, task in enumerate(tasks, 1):
            try:
                res = run_task(task, localizer, args.semantic, args.top_k)
            except Exception as e:  # noqa: BLE001
                res = {"task_id": task["task_id"], "repo": task["repo"], "error": repr(e)}
                print(f"[{i}/{len(tasks)}] {task['task_id']}: ERROR {e!r}")
            else:
                parts = []
                for name, s in res["strategies"].items():
                    a = agg.setdefault(name, {"n": 0, "gemma": 0, "gate": 0, "top1": 0})
                    a["n"] += 1; a["gemma"] += s["gemma_hit"]
                    a["gate"] += s["gold_in_topk"]; a["top1"] += s["retr_top1_hit"]
                    parts.append(f"{name}: gemma={s['gemma_hit']} gate={s['gold_in_topk']} top1={s['retr_top1_hit']}")
                print(f"[{i}/{len(tasks)}] {task['task_id']:28s} | " + " | ".join(parts))
            f.write(json.dumps(res) + "\n"); f.flush()

    print("\n=== summary (rate over scored tasks) ===")
    for name, a in agg.items():
        n = max(1, a["n"])
        print(f"{name:9s} n={a['n']}  gemma_hit@1={a['gemma']/n:.3f}  "
              f"gold_in_top{args.top_k}={a['gate']/n:.3f}  retr_top1={a['top1']/n:.3f}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
