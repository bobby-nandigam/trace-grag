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

## RQ1 — lexical vs semantic vs graph retrieval for localization

**Run `run-20261112-103442` (24/24 tasks, 0 errors; E1/E2/E3 on every task).** Graphs
range from ~850 (requests) to ~25.9k nodes (sympy). mean [95% bootstrap CI].

| strategy | hit@1 | hit@5 | hit@10 | recall@10 | MRR | lat (s) |
|---|---|---|---|---|---|---|
| BM25 (E1)     | 0.208 [0.042,0.375] | 0.500 [0.292,0.708] | 0.583 [0.375,0.750] | 0.376 [0.228,0.538] | 0.310 [0.167,0.473] | 0.13 |
| Semantic (E2) | 0.333 [0.167,0.542] | 0.417 [0.208,0.625] | 0.542 [0.333,0.708] | 0.336 [0.192,0.481] | 0.405 [0.235,0.586] | 67.2 (med 46.9, max 212.8) |
| Graph (E3)    | 0.208 [0.042,0.375] | 0.500 [0.292,0.708] | 0.583 [0.375,0.750] | 0.376 [0.228,0.538] | 0.310 [0.169,0.471] | 0.18 |

**Findings (honest, CI-backed):**
- **F1 — graph expansion nets to zero.** E3 equals E1 exactly in aggregate (hit@k, recall)
  and to 3 decimals on MRR. It reshuffles per-task rankings on 10/24 tasks, but gains and
  losses cancel. Graph expansion does **not** improve localization here, at higher latency.
- **F2 — semantic is complementary, not dominant.** E2 improves hit@1 (0.333 vs 0.208) and
  MRR (0.405 vs 0.310) and recovers repos lexical misses (per-repo hit@10: xarray 1.00 vs
  0.50, astropy 0.50 vs 0.00), but regresses where lexical wins (scikit-learn 0.33 vs 1.00,
  pylint 0.50 vs 1.00) and has lower recall@10. Per-task MRR: wins 12 / losses 9 / ties 3.
  **All pairwise CIs overlap — no significant winner at n=24.**
- **F3 — semantic costs ~500× more** (median 46.9 s vs 0.09 s per issue; max 212.8 s on sympy).

**Implication:** under local constraints BM25 is the rational default (non-inferior, ~500×
cheaper); lexical–semantic **fusion** (the test-evidence term `T` + combined ranker), not
graph expansion, is the promising direction the next experiments must test.

> The earlier E1/E3-only run `run-20261107-130652` reported the same E3≈E1 finding; this
> run supersedes it by adding the E2 semantic condition on all 24 tasks.

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

- ✅ **E2 semantic retrieval** (`nomic-embed-text` via Ollama) — **done** (run above).
- E4 test-guided ranking + E5 full TRACE-GRAG with budget-aware compression.
- Ablations A1–A5.
- Tier-B patch-execution pilot (3–5 tasks) with the Gemma E2B agent (pending a servable
  `gemma4` on local hardware; see `docs/LIMITATIONS.md`).

Weights α,β,γ,δ for the combined ranker will be tuned on the **dev** split only.
