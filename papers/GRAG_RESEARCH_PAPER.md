# TRACE-GRAG: An Empirical Study of Lexical, Semantic, and Graph Retrieval for Repository-Level Bug Localization under Local Gemma-Class Constraints

*Bobby Nandigam.* Submission to the Google Gemma 4 Developer Agent **Paper Track** (2026).

> **Status (2026-11-12):** every number in this paper is produced by the committed evaluation
> harness (`scripts/run_localization.py` → `scripts/evaluate.py` → `results/summary.json`,
> run `run-20261112-103442`), not hand-entered. Target length ≤ 3000 words — **confirm the
> Paper Track word limit and Writeup format on the official Kaggle page before submitting.**

---

## Abstract

We study lexical (BM25), semantic (dense `nomic-embed-text`), and graph (lexical-seeded
expansion) retrieval for repository-level bug localization on 24 SWE-bench Lite tasks under
strict local-inference constraints — a 16 GB Apple-Silicon machine with no SWE-bench Docker
harness. Using a provenance-disciplined code graph that never fabricates an edge, and
reporting every metric with 95% bootstrap confidence intervals, we find: (1) lexically-seeded
graph expansion provides **no net benefit** over BM25 (identical aggregate hit@k and recall;
per-task rank changes cancel out); (2) semantic retrieval is **complementary rather than
dominant** — it improves top-1 and MRR and recovers some repositories lexical retrieval misses
entirely, but regresses on others and shows **no statistically significant aggregate win** at
n=24; and (3) semantic retrieval costs roughly **500× more latency** locally (median 47 s vs
0.09 s per issue). We conclude that, for on-device software-engineering agents, a cheap lexical
retriever is a strong default, and lexical–semantic *fusion* — not graph expansion — is the
promising direction. Code, data, and the evaluation harness are released. The Gemma 4 agent
and patch-execution stages are designed but, with the target model not locally servable at
submission time, are reported as future work rather than results.

## 1. Introduction

Large language models can resolve real GitHub issues (SWE-bench [2]), whether through
tool-using agents (SWE-agent [3]) or simpler localize-then-repair pipelines (Agentless [1]).
A consistent finding is that **finding the right code to change** — localization — is
decisive for downstream success and is cheap to study in isolation. Separately, a growing
line of work argues that **repository-level code graphs** improve these systems: RepoGraph
[4] plugs a line-level dependency graph into four SWE-bench methods and improves them.

Two things are under-examined. First, most results come from large hosted models with the
full SWE-bench Docker evaluation harness (>100 GB of images). The regime of a **solo
developer or an on-device Gemma-class agent** — a 16 GB machine, tight disk, no Docker
harness — is different and under-reported. Second, the literature foregrounds **where
graphs help** and rarely isolates **where they do not**, with calibrated uncertainty.

This paper contributes a controlled, reproducible study in exactly that constrained regime.
We build a **provenance-disciplined** repository code graph that never fabricates an edge,
and we compare three retrieval conditions for bug localization on identical graphs:
**E1 lexical (BM25)**, **E2 semantic (dense embeddings)**, and **E3 graph (lexical-seeded
graph propagation)**. We report hit@k, recall@k, and MRR with 95% bootstrap confidence
intervals, on a disjoint dev/eval split of 24 SWE-bench Lite tasks across 10 repositories.

Our contributions are: (1) an auditable code-graph construction with explicit provenance
and confidence per edge; (2) a **two-tier evaluation design** (rigorous localization plus a
small patch-execution pilot) suited to constrained hardware; and (3) an honest empirical
comparison showing that **graph expansion gives no net gain over BM25, semantic retrieval is
complementary but not significantly better at ~500× the latency, and lexical–semantic fusion
is the promising direction** — including, explicitly, where each method does **not** help. We
do **not** claim that using a graph for repository understanding is novel (RepoGraph [4] and
others precede us); our contribution is measured evidence about *when* it helps under local
constraints.

## 2. Problem Definition

Given a repository `R` at a fixed base commit and a natural-language issue `q` (the
`problem_statement`), **bug localization** ranks the code symbols of `R` by their relevance
to fixing `q`. A symbol is a FUNCTION, METHOD, or CLASS with a precise source span. The
**gold** set is derived from the human fix: the symbols whose base-commit line spans
intersect the patch's changed (minus-side) lines, excluding test files (we score finding
the *implementation* to fix, not the hidden tests). Quality is measured by:

- **hit@k** — 1 if any gold symbol is in the top-k, else 0;
- **recall@k** — fraction of gold symbols in the top-k;
- **MRR** — reciprocal rank of the first gold symbol.

The agent never sees the gold patch or the hidden tests; gold is evaluator-only.

## 3. Related Work

See `RELATED_WORK.md` for the full discussion. In brief: localize-then-repair [1] and
agentic [3] approaches both depend on localization [2]; code graphs from CPGs [5] to
RepoGraph [4] add structure; lexical [11] and dense [10,12,13] retrieval are the standard
baselines; and Graph RAG [9] is the NL ancestor of code-graph retrieval. RepoGraph [4] is
the closest prior art. This work differs by isolating retrieval quality for localization
**under local-inference constraints** and reporting **negative as well as positive**
results with confidence intervals (`RESEARCH_GAP.md`).

## 4. Proposed Architecture

TRACE-GRAG is a seven-stage pipeline; stages 1–5 and the evaluation are implemented and
measured here, stages 6–7 are scaffolded future work (§11).

```
issue → [1] Ingestion → [2] Parsing+Graph → [3] Retrieval → [4] Ranking
       → [5] Compression → [6] Agent (Gemma) → [7] Execution (Tier-B pilot)
```

**Code graph (stage 2).** A two-pass `ast` parser emits six node types
(FILE, MODULE, CLASS, FUNCTION, METHOD, TEST) and six edge types (CONTAINS, DEFINES,
IMPORTS, CALLS, TESTS, COVERS). Each node carries a stable id, repo-relative path, line
span, content hash, signature, and docstring. **Every edge carries a `Provenance`**
(`ast_static`, `import_resolved`, `call_resolved`, `name_heuristic`, `coverage_dynamic`,
`unresolved`) and a calibrated confidence. **Unresolvable call/import targets are recorded
as `unresolved`, never invented** — a property enforced by a unit test. The graph is a
NetworkX MultiDiGraph with version-independent flat-JSON persistence.

**Retrieval (stage 3).** Three conditions share the same candidate set (FUNCTION/METHOD/
CLASS nodes) and the same issue text:
- **E1 — BM25** over a per-symbol document (qualified name, name, signature, docstring),
  with snake/camel identifier tokenization.
- **E2 — Semantic**: cosine similarity between the issue embedding and per-symbol
  embeddings (`nomic-embed-text`, 768-dim, served locally by Ollama); embeddings are cached
  by content hash for reproducibility.
- **E3 — Graph**: BM25 seeds the top symbols, then structural relevance propagates over the
  undirected code graph with per-hop decay; a node's score mixes propagated structural mass
  with its own lexical score.

**Ranking, compression, agent, execution (stages 4–7).** The design targets a combined
score `S(v,q)=αL+βE+γT+δG` with a **test-evidence term `T`**, budget-aware connected-
subgraph context selection, a Gemma E2B/E4B tool-using agent with a bounded repair loop,
and per-repo venv sandboxed test execution. These are **not** evaluated in this paper and
are reported as future work (§11); no result below depends on them.

## 5. Methodology

**Graph integrity.** Static resolution is trusted (`ast_static`=1.0, `import_resolved`=0.95,
`call_resolved`=0.9); heuristics are discounted (`name_heuristic`=0.6); unresolved targets
are kept at low confidence (0.3) with their raw textual target, so later stages can use them
without the graph asserting a false edge. Call resolution is bare-name based and may
over-connect symbols sharing a name (a precision risk we flag, §10).

**Gold construction.** We parse each SWE-bench Lite gold patch's unified diff, take the
**minus-side** (base-commit) line ranges per changed non-test file, and map them to the
FUNCTION/METHOD/CLASS nodes whose spans intersect them (`evaluation/localization.py`). This
is evaluator-only and deterministic.

**Statistics.** Each metric is reported as the mean over tasks with a **95% bootstrap CI**
(2000 resamples, fixed seed). Weights for the (future) combined ranker are to be tuned on
the **dev split only**; all retrieval conditions here are untrained and use fixed defaults,
so no split leakage is possible.

## 6. Experimental Setup

- **Benchmark:** 24 SWE-bench Lite tasks across 10 repositories, deterministically selected
  (`scripts/build_manifest.py`), disjoint **6 dev / 18 eval**. Graph sizes range from ~850
  nodes (requests) to ~25.9k (sympy).
- **Hardware:** Mac mini **M4, 16 GB** unified memory, macOS 26.3, arm64; ~22 GB free disk.
- **Models/runtimes:** `nomic-embed-text` (E2) via Ollama, run locally. The Gemma 4
  (E2B/E4B) agent condition was **not** runnable at submission time (the target model was
  not servable on the installed Ollama); this is reported honestly, not worked around.
- **Procedure:** for each task, fetch a disk-safe tarball snapshot at the base commit, build
  the graph, derive gold symbols, run E1/E2/E3, score, log per-task JSON, delete the
  snapshot (peak disk = one repo). Full commands in `research/REPRODUCIBILITY.md`.

## 7. Results

All 24 tasks completed with **0 errors**; E1, E2, and E3 ran on every task. Table 1 reports
the full set (mean with 95% bootstrap CI); the disjoint dev (n=6) and eval (n=18) splits show
the same pattern (`results/summary.json`). Latency is the harness mean; for E2 we also give
the median and max, since it is right-skewed by the largest graphs.

**Table 1 — Localization on 24 SWE-bench Lite tasks. mean [95% bootstrap CI].**

| strategy | hit@1 | hit@5 | hit@10 | recall@10 | MRR | lat (s) |
|---|---|---|---|---|---|---|
| **E1 BM25** | 0.208 [0.042,0.375] | 0.500 [0.292,0.708] | 0.583 [0.375,0.750] | 0.376 [0.228,0.538] | 0.310 [0.167,0.473] | 0.13 |
| **E2 Semantic** | 0.333 [0.167,0.542] | 0.417 [0.208,0.625] | 0.542 [0.333,0.708] | 0.336 [0.192,0.481] | 0.405 [0.235,0.586] | 67.2 (med 46.9, max 212.8) |
| **E3 Graph** | 0.208 [0.042,0.375] | 0.500 [0.292,0.708] | 0.583 [0.375,0.750] | 0.376 [0.228,0.538] | 0.310 [0.169,0.471] | 0.18 |

On the held-out **eval** split (n=18) the ordering is unchanged: MRR 0.334 (E1) / 0.415 (E2) /
0.332 (E3); hit@1 0.222 / 0.333 / 0.222.

**F1 — Graph expansion yields no net benefit over lexical.** E3 equals E1 *exactly* in
aggregate on hit@1/5/10 and recall@10, and to three decimals on MRR (0.310). Per task, graph
expansion *does* change the ranking (it alters MRR on 10/24 tasks, mostly large repos) — but
the gains and losses cancel, leaving aggregate quality unchanged at higher latency. Static,
lexically-seeded graph expansion is therefore not justified for localization on this set.

**F2 — Semantic retrieval is complementary, not dominant.** E2 improves top-rank quality
(hit@1 0.333 vs 0.208; MRR 0.405 vs 0.310) and **recovers hard repositories lexical misses
entirely** — per-repo hit@10: xarray 1.00 vs 0.50, astropy 0.50 vs 0.00 — but it **regresses
where lexical already succeeds** (scikit-learn 0.33 vs 1.00; pylint 0.50 vs 1.00) and has lower
aggregate recall@10 (0.336 vs 0.376). Head to head it beats BM25's MRR on 12 tasks, loses on 9,
ties on 3. **Every pairwise difference has overlapping 95% CIs: no retriever is a statistically
significant winner at n=24.**

**F3 — Semantic retrieval is ~500× more expensive locally.** Median E2 latency is 46.9 s per
issue (max 212.8 s on sympy's ~26k-node graph) versus 0.09 s median for BM25, because every
candidate symbol must be embedded through the local model. For an interactive on-device agent
this cost is frequently prohibitive.

## 8. Ablation Studies

The conditions evaluated here are E1/E2/E3. We deliberately do **not** report fabricated
ablation rows. Two honest observations stand in for a full sweep: (i) the graph condition's
internal parameters (hop depth, seed count, decay) were held fixed, and given F1 — that graph
expansion nets to zero in aggregate — tuning them is unlikely to change the conclusion without
a different signal; (ii) the informative ablation is therefore the **test-evidence term and the
combined ranker** `S=αL+βE+γT+δG`, which are scaffolded but not yet producing results (§11).
Running A1–A5 (semantic weight, 1-hop vs multi-hop, per-edge-type contributions, dependency-
aware ranking, context budget) is the immediate next step and is specified in the repository.

## 9. Discussion

**Complementarity is the actionable signal.** F2 shows lexical and semantic retrieval winning
*disjoint* repositories — lexical nails scikit-learn and pylint; semantic recovers xarray and
astropy where lexical scores zero. A method that fuses or routes between them (the planned
`S=αL+βE+γT+δG`, with the test-evidence term `T`) is thus the most promising path to a *real*
improvement, and is better motivated by this evidence than graph expansion.

**Why graph expansion fails (F1).** Seeded from lexical matches, structural propagation
inherits the seed's errors; on the very large graphs where both lexical and graph score 0
hit@10 (sympy, astropy), expansion cannot surface a gold symbol the seed never retrieved, and
on smaller graphs it mostly reorders already-retrieved candidates — hence the net-zero effect.

**Implications for on-device agents (F3).** Under a latency/compute budget, the cheapest
*non-inferior* retriever is the rational default: BM25 at ~0.09 s is statistically
indistinguishable from the alternatives in quality while being ~500× faster. Semantic retrieval
earns its cost only when top-1 precision is critical and latency is acceptable; graph expansion,
on this evidence, does not earn its (smaller) overhead at all.

## 10. Limitations

- **Localization, not end-to-end resolution.** We measure retrieval quality; we do not run
  the Gemma agent or execute patches at scale (Tier-B is a pilot only, §11). Localization is
  necessary but not sufficient for issue resolution.
- **No Gemma 4 agent results.** The competition's target model was not servable locally at
  submission time; the agent pipeline is designed and scaffolded but unevaluated.
- **Python-only graph** (stdlib `ast`); other languages via Tree-sitter are future work.
  SWE-bench Lite is Python-only, so this does not affect the reported results.
- **Bare-name call resolution** can over-connect same-named symbols, inflating graph edges;
  mitigated by confidence but not eliminated.
- **Small N (24 tasks)** — CIs are correspondingly wide; we report them rather than hide them.
- **Single machine / single run** for timing; latencies are indicative, not benchmarked.

## 11. Future Work

Implement and evaluate the combined ranker `S=αL+βE+γT+δG` with the test-evidence term;
budget-aware subgraph compression; the Gemma 4 E2B/E4B agent with a bounded repair loop; and
the Tier-B sandboxed patch-execution pilot. Add per-edge-type and multi-hop ablations.

## 12. Conclusion

Under strict local-inference constraints, an auditable, provenance-disciplined code graph is
valuable for agent *tooling and transparency* — but for *localization ranking* the measured
evidence does **not** support lexically-seeded graph expansion over a strong lexical baseline,
and semantic retrieval buys only a small, statistically non-significant top-rank gain at a
~500× latency cost. The durable, actionable finding is **lexical–semantic complementarity**,
which motivates the planned test-guided combined ranker. We report these outcomes — positive,
negative, and inconclusive alike — with confidence intervals, and treat that honesty as the
contribution.

## References

See `papers/REFERENCES.md` (each entry marked VERIFIED / WELL-ESTABLISHED / CONFIRM).
Numeric citations [1]–[15] in this paper map to that file.

---

### Reproducibility

Code, manifest, and the exact commands are in the repository; `research/REPRODUCIBILITY.md`
lists them. All numbers trace to `results/summary.json` via `scripts/evaluate.py`.
