# Reproducibility

Everything needed to reproduce the localization results. All numbers in the paper trace to
`results/summary.json`, produced by `scripts/evaluate.py` from a raw run log under
`results/localization/`. No number is hand-entered.

## Environment

- Python 3.12 (3.11+ supported). macOS arm64 (M4, 16 GB) used for the reported runs.
- Core deps pinned by `pyproject.toml`: networkx≥3, pydantic≥2, numpy, rank-bm25, pyyaml.
- Eval extras: `pandas`, `scikit-learn`, `matplotlib` (only for analysis/plots).
- E2 semantic retrieval needs a local **Ollama** serving `nomic-embed-text` (768-dim).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[eval,dev]"
python -m pytest -q          # expect: all tests pass
```

For E2 only:
```bash
ollama serve &               # daemon on :11434
ollama pull nomic-embed-text # 274 MB
curl -s localhost:11434/api/embed -d '{"model":"nomic-embed-text","input":["ping"]}' | head -c 80
```

## Reproduce the benchmark manifest (deterministic)

```bash
python scripts/build_manifest.py        # writes data/benchmark_manifest.jsonl (24 tasks)
```

## Run localization (Tier A)

```bash
# E1 (BM25) + E3 (graph) only — no Ollama needed, fully reproducible offline:
python scripts/run_localization.py

# Add E2 (semantic) — requires the Ollama embedding backend:
python scripts/run_localization.py --semantic --keep-graph

# Subsets:
python scripts/run_localization.py --split dev
python scripts/run_localization.py --repos psf/requests pallets/flask --limit 2
```

Each run writes `results/localization/run-<timestamp>.jsonl` (one JSON object per task).
A strategy that fails on a task (e.g. the embedding backend erroring) is recorded under that
task's `strategy_errors` and does **not** discard the other strategies' results.

## Aggregate with bootstrap CIs

```bash
python scripts/evaluate.py                                   # newest run
python scripts/evaluate.py results/localization/run-<ts>.jsonl
# writes results/summary.json and prints all/dev/eval tables with 95% bootstrap CIs
```

## Determinism notes

- Bootstrap CIs use a fixed seed (2000 resamples) → identical given the same run log.
- E1/E3 are deterministic. E2 embeddings are deterministic per model version but depend on
  the exact `nomic-embed-text` build served by Ollama; record the model digest
  (`ollama list`) alongside results for exact reproduction.
- Snapshots are fetched at pinned base commits (`data/benchmark_manifest.jsonl`) and deleted
  after each task (peak disk ≈ one repo), so disk stays within the ~22 GB budget.

## What is NOT reproducible here (honest scope)

- The Gemma 4 (E2B/E4B) agent and Tier-B patch execution were not runnable at submission
  time (target model not servable on the available Ollama); see `docs/LIMITATIONS.md`.
