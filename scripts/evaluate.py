#!/usr/bin/env python
"""
Aggregate a localization run into a summary table with bootstrap 95% CIs.

Usage:
  python scripts/evaluate.py results/localization/run-YYYYMMDD-HHMMSS.jsonl
  python scripts/evaluate.py              # newest run in results/localization
"""
from __future__ import annotations

import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ["hit@1", "hit@5", "hit@10", "recall@10", "mrr"]


def bootstrap_ci(values: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    if not values:
        return (0.0, 0.0, 0.0)
    rnd = random.Random(seed)
    means = []
    for _ in range(n):
        sample = [values[rnd.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    mean = sum(values) / len(values)
    lo = means[int(0.025 * n)]
    hi = means[int(0.975 * n)]
    return (mean, lo, hi)


def load_run(path: str) -> list[dict]:
    return [json.loads(l) for l in open(path)]


def summarize(rows: list[dict], split: str | None = None) -> dict:
    rows = [r for r in rows if "error" not in r and (split is None or r["split"] == split)]
    strategies = sorted({s for r in rows for s in r["strategies"]})
    table: dict[str, dict] = {}
    for strat in strategies:
        table[strat] = {}
        for m in METRICS:
            vals = [r["strategies"][strat][m] for r in rows if strat in r["strategies"]]
            table[strat][m] = bootstrap_ci(vals)
        lat = [r["strategies"][strat]["latency_s"] for r in rows if strat in r["strategies"]]
        table[strat]["latency_s"] = (sum(lat) / len(lat), min(lat), max(lat)) if lat else (0, 0, 0)
    return {"n": len(rows), "table": table}


def fmt(ci: tuple[float, float, float]) -> str:
    m, lo, hi = ci
    return f"{m:.3f} [{lo:.3f},{hi:.3f}]"


def main() -> None:
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        runs = sorted(glob.glob(str(ROOT / "results" / "localization" / "run-*.jsonl")))
        if not runs:
            print("no runs found"); return
        path = runs[-1]
    rows = load_run(path)
    n_err = sum(1 for r in rows if "error" in r)
    print(f"# Localization summary — {Path(path).name}")
    print(f"tasks: {len(rows)} ({n_err} errors)\n")

    for split in ("all", "dev", "eval"):
        s = summarize(rows, None if split == "all" else split)
        print(f"## {split} (n={s['n']})  —  metric: mean [95% bootstrap CI]")
        header = f"{'strategy':10s} | " + " | ".join(f"{m:^22s}" for m in METRICS) + " | lat(s)"
        print(header)
        print("-" * len(header))
        for strat, md in s["table"].items():
            cells = " | ".join(f"{fmt(md[m]):22s}" for m in METRICS)
            print(f"{strat:10s} | {cells} | {md['latency_s'][0]:.2f}")
        print()

    # per-repo hit@10 (generalization, RQ4)
    print("## per-repo hit@10 (bm25 / graph)")
    by_repo: dict[str, list[dict]] = {}
    for r in rows:
        if "error" not in r:
            by_repo.setdefault(r["repo"], []).append(r)
    for repo in sorted(by_repo):
        rs = by_repo[repo]
        b = sum(r["strategies"]["bm25"]["hit@10"] for r in rs) / len(rs)
        g = sum(r["strategies"]["graph"]["hit@10"] for r in rs) / len(rs)
        print(f"  {repo:26s} n={len(rs)}  bm25={b:.2f}  graph={g:.2f}")

    out = ROOT / "results" / "summary.json"
    full = {split: summarize(rows, None if split == "all" else split)
            for split in ("all", "dev", "eval")}
    out.write_text(json.dumps({"run": Path(path).name, "summaries": full}, indent=2, default=list))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
