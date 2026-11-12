#!/usr/bin/env python
"""
Build a pinned, reproducible benchmark manifest from SWE-bench Lite.

Selection is deterministic (first N instance_ids per repo, sorted) so the manifest
is byte-stable across runs. Repos favor small pure-Python projects (cheap Tier-B
execution) plus several larger ones for the generalization question (RQ4).

Writes data/benchmark_manifest.jsonl with one record per task:
  task_id, repo, base_commit, environment_setup_commit, version, split,
  problem_statement, gold_files, gold_line_ranges, fail_to_pass, pass_to_pass,
  dataset_source. The gold_* fields are evaluator-only (never shown to the agent).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trace_grag.evaluation.localization import parse_patch  # noqa: E402

# repo -> number of tasks to select
SELECTION = {
    "psf/requests": 3,
    "pallets/flask": 2,
    "pytest-dev/pytest": 3,
    "sphinx-doc/sphinx": 2,
    "sympy/sympy": 4,
    "scikit-learn/scikit-learn": 3,
    "astropy/astropy": 2,
    "pydata/xarray": 2,
    "pylint-dev/pylint": 2,
    "mwaskom/seaborn": 1,
}
# One task from each of these repos is held out as dev (for tuning weights only).
DEV_REPOS = {"psf/requests", "pytest-dev/pytest", "sympy/sympy",
             "scikit-learn/scikit-learn", "astropy/astropy", "pydata/xarray"}

OUT = Path(__file__).resolve().parents[1] / "data" / "benchmark_manifest.jsonl"


def main() -> None:
    os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[1] / ".hfcache"))
    from datasets import load_dataset

    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    by_repo: dict[str, list[dict]] = {}
    for row in ds:
        by_repo.setdefault(row["repo"], []).append(row)

    records = []
    for repo, k in SELECTION.items():
        rows = sorted(by_repo.get(repo, []), key=lambda r: r["instance_id"])[:k]
        for i, r in enumerate(rows):
            gold = parse_patch(r["patch"])
            split = "dev" if (repo in DEV_REPOS and i == 0) else "eval"
            records.append({
                "task_id": r["instance_id"],
                "repo": repo,
                "base_commit": r["base_commit"],
                "environment_setup_commit": r["environment_setup_commit"],
                "version": r["version"],
                "split": split,
                "problem_statement": r["problem_statement"],
                "gold_files": gold.files,
                "gold_line_ranges": {f: gold.line_ranges[f] for f in gold.files},
                "fail_to_pass": json.loads(r["FAIL_TO_PASS"]),
                "pass_to_pass": json.loads(r["PASS_TO_PASS"]),
                "dataset_source": "princeton-nlp/SWE-bench_Lite:test",
            })

    records.sort(key=lambda x: x["task_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    n_dev = sum(1 for r in records if r["split"] == "dev")
    print(f"wrote {len(records)} tasks ({n_dev} dev / {len(records)-n_dev} eval) to {OUT}")
    print(f"repos: {len(SELECTION)}")
    # sanity: every task has >=1 gold file
    missing = [r["task_id"] for r in records if not r["gold_files"]]
    if missing:
        print(f"WARNING: {len(missing)} tasks have no non-test gold file: {missing}")
    else:
        print("all tasks have >=1 non-test gold file")


if __name__ == "__main__":
    main()
