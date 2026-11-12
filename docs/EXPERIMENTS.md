# Experiments

All numbers are produced by `scripts/run_localization.py` + `scripts/evaluate.py`
and logged under `results/localization/`. Nothing here is hand-entered.

## Setup

- **Benchmark:** 24 SWE-bench Lite tasks across 10 repos (`data/benchmark_manifest.jsonl`),
  disjoint 6-dev / 18-eval split. Deterministic selection (see `scripts/build_manifest.py`).
- **Tier A (localization):** build the repo graph at the base commit, derive gold
  symbols from the gold patch's base-commit line ranges (`evaluation/localization.py`),
  rank candidate FUNCTION/METHOD/CLASS nodes, score hit@k / recall@k / MRR.
- **Gold:** evaluator-only. The agent never sees the gold patch or the hidden tests.
- Metrics report mean with a 95% bootstrap CI (2000 resamples).

## RQ1 — does graph retrieval beat lexical retrieval for localization?

**Run `run-20261107-130652` (24/24 tasks, 0 errors).** Each gold task has ≥1
non-test gold file; graphs range from ~850 (requests) to ~25.9k nodes (sympy).

| strategy | hit@1 | hit@5 | hit@10 | recall@10 | MRR | lat (s) |
|---|---|---|---|---|---|---|
| BM25 (E1)  | 0.208 | 0.500 | 0.583 [0.375,0.750] | 0.376 | 0.310 | 0.13 |
| Graph (E3) | 0.208 | 0.500 | 0.583 [0.375,0.750] | 0.376 | 0.310 | 0.17 |

**Finding (preliminary, honest):** static graph expansion seeded from lexical
matches is **statistically indistinguishable from BM25** for localization on this
set — identical hit@k and essentially identical MRR, with a small latency cost.
Graph expansion alone does **not** improve localization here. This is the baseline
that the test-evidence term (Contribution 2) and budget-aware connected-subgraph
selection (Contribution 3) must improve upon to justify their inclusion.

### Per-repo hit@10 (generalization signal, RQ4)

| repo | n | hit@10 |
|---|---|---|
| pallets/flask | 2 | 1.00 |
| pylint-dev/pylint | 2 | 1.00 |
| pytest-dev/pytest | 3 | 1.00 |
| scikit-learn/scikit-learn | 3 | 1.00 |
| psf/requests | 3 | 0.67 |
| pydata/xarray | 2 | 0.50 |
| sphinx-doc/sphinx | 2 | 0.50 |
| astropy/astropy | 2 | 0.00 |
| sympy/sympy | 4 | 0.00 |
| mwaskom/seaborn | 1 | 0.00 |

**Observation:** both methods succeed on small/medium repos and fail on the
largest graphs (sympy ~24k nodes, astropy ~19k). Localization in very large repos
is the open hard case — a strong motivation for test-guided narrowing.

## Planned (not yet run)

- E2 semantic retrieval (`nomic-embed-text` via Ollama, already local).
- E4 test-guided ranking + E5 full TRACE-GRAG with budget-aware compression.
- Ablations A1–A5.
- Tier-B patch-execution pilot (3–5 tasks) with the Gemma E2B agent.

Weights α,β,γ,δ for the combined ranker will be tuned on the **dev** split only.
