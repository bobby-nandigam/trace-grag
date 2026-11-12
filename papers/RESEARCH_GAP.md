# Research Gap & Novelty Statement

## What the literature already establishes (NOT claimed here)

- Repository graphs improve LLM software-engineering systems (RepoGraph [4]).
- Localization + repair is a strong, cheap recipe (Agentless [1]).
- Lexical and dense retrieval are well-understood baselines (BM25 [11], DPR [10]).

We **explicitly do not** claim "using a graph for repository understanding" as novel.

## The actual gap this work addresses

Three things are under-reported in the graph-for-SE literature, and are where this work
contributes honest, measured evidence:

1. **A controlled, CI-level comparison under local-inference constraints.** Most prior
   work reports end-to-end resolution with large hosted models and the full SWE-bench
   Docker harness. This work isolates **retrieval quality for localization** on identical
   graphs, with lexical / semantic / graph conditions held otherwise equal, on a **16 GB
   Apple-Silicon machine with ~22 GB free disk** — the regime a solo developer or a
   Gemma-class on-device agent actually operates in. The two-tier design (rigorous
   localization + a small patch-execution pilot) is a reusable template for this regime.

2. **A negative/neutral result made explicit.** On this task set, **static graph
   expansion seeded from lexical matches does not beat BM25 for localization** (reported
   with bootstrap CIs). The "graphs help" narrative rarely surfaces where they do *not*,
   and *why* (graph expansion inherits the seed's errors and dilutes precision on very
   large graphs). Reporting this honestly is a contribution in itself.

3. **A provenance-disciplined code graph that never invents edges.** Every edge records
   how it was derived (`ast_static`, `import_resolved`, `call_resolved`, `name_heuristic`,
   `coverage_dynamic`, `unresolved`) and a calibrated confidence; unresolved call/import
   targets are recorded as `unresolved` rather than fabricated. This makes the graph
   auditable and is a prerequisite for trustworthy agent tools.

## Honest scope boundary (what is future work, not results)

The following are **designed and partially scaffolded but not yet producing results**, and
are reported as future work — **not** as contributions with evidence:

- The dependency-aware combined ranker `S = αL + βE + γT + δG` with a **test-evidence term
  `T`** (the `ranking/` and `compression/` modules are stubs).
- Budget-aware connected-subgraph context compression.
- The **Gemma 4 (E2B/E4B) agent**, patch generation, and **Tier-B sandboxed execution**
  (the target model `gemma4` was not servable on the available Ollama at submission time).

## One-line novelty claim (as it will appear in the paper)

> A reproducible, provenance-disciplined study of lexical vs. semantic vs. graph retrieval
> for repository-level bug localization under strict local-inference constraints, which
> reports — with confidence intervals — **where graph expansion helps and where it does
> not**, rather than assuming it always helps.
