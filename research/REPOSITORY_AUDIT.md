# Phase 1 — Repository Audit

**Audited repository:** `/Users/bobbynandigam/Projects/trace-grag` (local, **not** `grag_system`)
**Audit date:** 2026-11-12
**Auditor mode:** read-only inspection. No source file was modified in this phase.
**Test result at audit time:** `15 passed in 0.31s`.

---

## 0. Important framing — which repository is "the existing GRAG repo"?

The brief names `https://github.com/bobby-nandigam/grag_system` as "my existing GRAG
repository." That repository is **not present on this machine** and was **not** the
subject of this audit. What is on disk is a **separate, more advanced project**,
`trace-grag` (created 2026-11-07), which has **already** audited `grag_system` and
begun the research extension.

Concretely, `grag_system` is the **prior** project; `trace-grag` is the **research
extension in progress**. This is documented inside the repo itself at
`docs/EXISTING_GRAG_AUDIT.md`, which audited `grag_system` (MIT, v1.1.0, ~2,680 LOC)
from a read-only clone and recorded exactly what is inherited vs. new.

**Re-verified directly against the live GitHub repo on 2026-11-12** (read-only
`--depth 1` clone into a scratch dir; the GitHub repo was not modified). Every claim
in `docs/EXISTING_GRAG_AUDIT.md` checks out exactly: MIT license ✓, `version = 1.1.0` ✓,
`grag/` = **exactly 2,680 LOC** ✓, all module names present ✓, and the README confirms
it is a natural-language Graph-RAG **question-answering** system (KG + RL + critic +
memory) with **no code/AST/repository awareness**. Last pushed 2026-07-12, default
branch `main` (`dd20660`). The prior audit is faithful, not second-hand guesswork.

**Consequence for the plan:** the generic 11-phase brief assumes a greenfield
extension of `grag_system`. In reality, Phases 1–7 are **substantially already done**
in `trace-grag`. Blindly re-running the template would duplicate and risk
contradicting existing, honestly-reported work. Recommended adjustments are in §7.

---

## 1. Repository state

| Property | Value |
|---|---|
| Path | `/Users/bobbynandigam/Projects/trace-grag` |
| Git | initialized, **0 commits**, **no remote**, everything untracked |
| Python | 3.12.13 in `.venv` |
| Package | `trace-grag` 0.1.0, `src/` layout, Apache-2.0 |
| Core deps | networkx≥3, pydantic≥2, pyyaml, numpy, rank-bm25 |
| Optional | `dev` (pytest, coverage) installed; `eval` (pandas/sklearn/matplotlib) **NOT installed** |
| Tests | 15 tests, **all passing** (`pythonpath=["src"]`; package not `-e` installed) |
| Secrets | none found (grep over py/md/toml/yaml/json) |
| Source size | ~1,184 LOC across `src/` + scripts |

### Layout (excl. venv/caches)
```
src/trace_grag/
  graph/        schema.py, repo_graph.py          ✅ complete
  parsing/      python_parser.py (ast, 2-pass)    ✅ complete
  ingestion/    snapshot.py (safe tarball)        ✅ complete
  retrieval/    base.py, lexical.py (E1),         ✅ E1,E3
                graph_retrieval.py (E3)
  evaluation/   localization.py, metrics.py       ✅ complete
  ranking/      __init__.py                        ⛔ EMPTY (stub)
  compression/  __init__.py                        ⛔ EMPTY (stub)
  agent/        __init__.py                        ⛔ EMPTY (stub)
  utils/        __init__.py                        ⛔ EMPTY (stub)
scripts/        build_manifest.py, run_localization.py, evaluate.py
data/           benchmark_manifest.jsonl (24 SWE-bench Lite tasks), sample/minirepo
results/        localization/*.jsonl, summary.json, grag_graph.json
docs/           ARCHITECTURE, EXPERIMENTS, EXISTING_GRAG_AUDIT, LIMITATIONS
tests/          test_graph_pipeline.py (9), test_retrieval.py (6)
```

---

## 2. What already works (verified, reusable)

1. **Graph schema** (`graph/schema.py`) — Pydantic models, 6 node types
   (FILE/MODULE/CLASS/FUNCTION/METHOD/TEST), 6 edge types
   (CONTAINS/DEFINES/IMPORTS/CALLS/TESTS/COVERS), a `Provenance` enum, and
   per-provenance default confidences. **Unresolved targets are recorded as
   `UNRESOLVED`, never invented** — this integrity rule is enforced by a test.
2. **Python parser** (`parsing/python_parser.py`) — stdlib `ast`, two-pass (symbol
   table → edges), nearest-enclosing-scope call attribution, naming-heuristic TESTS
   edges, safe handling of unparseable files. Dependency-free and version-matched.
3. **RepoGraph** (`graph/repo_graph.py`) — NetworkX `MultiDiGraph`, name index,
   k-hop neighbors, connected-subgraph, version-independent flat JSON persistence
   (roundtrip test passes). Mirrors GRAG's proven storage pattern with a code schema.
4. **Snapshot ingestion** (`ingestion/snapshot.py`) — GitHub `codeload` tarball at a
   pinned commit, **path-traversal-guarded** extraction, cleanup for disk budget.
   Snapshots are parsed with `ast` only, never executed (isolation for untrusted code).
5. **Retrieval E1 + E3** — BM25 lexical (`lexical.py`) and lexical-seeded graph
   propagation with hop decay (`graph_retrieval.py`), restricted to localization
   targets (FUNCTION/METHOD/CLASS).
6. **Localization ground truth + metrics** (`evaluation/`) — parses the gold patch's
   **minus-side** (base-commit) line ranges, excludes test files, maps ranges to
   overlapping symbol nodes; hit@k / recall@k / MRR. Evaluator-only (agent never sees gold).
7. **Benchmark + harness** — 24 pinned SWE-bench Lite tasks (6 dev / 18 eval),
   deterministic manifest, run+evaluate scripts, bootstrap-CI aggregation.
8. **Honest results already recorded** — `docs/EXPERIMENTS.md` + `results/summary.json`:
   on 24/24 tasks, **E3 graph retrieval is statistically indistinguishable from E1
   BM25** for localization (identical hit@k, near-identical MRR, small latency cost).
   This is reported as a preliminary negative/neutral finding, not hidden.

---

## 3. Missing / stubbed research capabilities

Mapped to the brief's phases and the repo's own `S(v,q)=αL+βE+γT+δG` design:

| # | Capability | State | Where it belongs |
|---|---|---|---|
| M1 | **E2 semantic retrieval** (embeddings, e.g. `nomic-embed-text` via Ollama) | ⛔ not implemented | `retrieval/semantic.py` |
| M2 | **E4 test-guided ranking** (`T` term; COVERS from coverage) | ⛔ not implemented | `ranking/` |
| M3 | **Combined ranker** `S=αL+βE+γT+δG` (normalized, dev-tuned weights) | ⛔ empty stub | `ranking/` |
| M4 | **Budget-aware connected-subgraph compression** (Contribution 3) | ⛔ empty stub | `compression/` |
| M5 | **Gemma 4 (E2B/E4B) agent** + tools + bounded repair loop | ⛔ empty stub | `agent/` |
| M6 | **Patch generation + Tier-B sandboxed execution** pilot | ⛔ not implemented | `agent/` + sandbox |
| M7 | **Ablations A1–A5** (semantic / 1-hop / multi-hop / per-edge-type / depth / budget) | ⛔ not run | `scripts/` |
| M8 | **Patch-success / test-pass / regression metrics** | ⛔ not implemented | `evaluation/` |
| M9 | Literature review docs (RELATED_WORK, RESEARCH_GAP, REFERENCES) | ⛔ not present | `papers/` |
| M10 | Research paper draft | ⛔ not present | `papers/` |

**Secondary gaps / risks:**
- `eval` optional deps not installed in `.venv` → `scripts/evaluate.py` won't run here
  until `pip install -e ".[eval]"`.
- Package not installed editable → external `import trace_grag` fails (tests mask this
  via `pythonpath`). Fine for tests, a snag for scripts run outside pytest.
- **Gemma 4 inference is unverified** — `LIMITATIONS.md` records Ollama 0.18.2 cannot
  yet serve `gemma4` (needs ≥0.22 upgrade); no model pulled. **Do not assume local
  inference works** until verified. Disk is the binding constraint (~21 GB free).

---

## 4. Architectural limitations (by design, documented)

- **Python-only graph** (stdlib `ast`); JS/TS via Tree-sitter is deferred future work.
  Acceptable because SWE-bench Lite is Python-only.
- **No full SWE-bench Docker harness** (>100 GB images vs. 21 GB free) → two-tier eval:
  Tier A localization (rigorous, full set) + Tier B patch execution (small-N pilot).
- Call resolution is **bare-name based** (`_by_bare[callee.split('.')[-1]]`) → can
  over-connect when a name is defined in multiple modules; mitigated by confidence,
  but a precision risk worth measuring in an ablation.
- TESTS edges are naming-heuristic only (confidence 0.6) until coverage (COVERS) exists.

---

## 5. Technical risks

| Risk | Severity | Mitigation |
|---|---|---|
| Gemma 4 E2B may not fit/serve on 16 GB + Ollama ≤0.18 | **High** | Verify Ollama upgrade + model pull before Phase 5 agent work; E4B only if memory permits |
| Disk (~21 GB free) exhausted by snapshots/models | **High** | Snapshot cleanup already built; cap concurrent snapshots; prune `.hfcache` |
| E3 already == E1 → graph story may not hold | **Medium** | The honest result stands; E4 (test) + compression must earn their place or be reported negative |
| Bare-name call over-linking inflates graph edges | **Medium** | Add a precision ablation; consider scope-aware resolution |
| Novelty overlap with RepoGraph/GraphRAG prior art | **Medium** | `EXISTING_GRAG_AUDIT.md` already scopes the claim to issue-conditioning + test-guided + budget-aware subgraph under local E2B/E4B |
| No commits / no remote → work is unprotected | **Low/High** | Recommend an initial commit + push early (see §7) |

---

## 6. Reuse map — `grag_system` → `trace-grag`

Credited engineering patterns inherited (per `docs/EXISTING_GRAG_AUDIT.md`), **not**
claimed as novel: NetworkX MultiDiGraph store + flat-JSON persistence; per-edge
confidence/provenance; `get_neighbors` / `extract_subgraph`; hybrid multi-signal
retrieval (ancestor of `S=αL+βE+γT+δG`); abstention-over-fabrication safety; config-
dataclass + tunable-weights discipline. GRAG's Q&A-specific machinery (RL reward,
critic, memory, query-understanding, contradiction detection) is **deliberately not
carried over** — it does not fit repo-level SE.

---

## 7. Recommended implementation sequence (for your review)

The repo's own `README` status table and `docs/EXPERIMENTS.md` "Planned" section
already imply this order; it matches the brief's phases with the duplication removed:

1. **Install `eval` extras + editable package**, add an initial git commit (protect work). *(trivial, do first)*
2. **M1 — E2 semantic retrieval** (`nomic-embed-text` via Ollama, already local). Reuses the `Retriever` protocol.
3. **M2/M3 — `T` term + combined ranker** in `ranking/`; tune α,β,γ,δ on the **dev split only**.
4. **M4 — budget-aware compression** in `compression/` (Contribution 3).
5. **Re-run Tier A** (E1–E5 + ablations M7) with bootstrap CIs; update `EXPERIMENTS.md` honestly.
6. **M5/M6 — Gemma agent + Tier-B pilot**, *only after* verifying Ollama/`gemma4` serving and disk.
7. **M8 — patch/test/regression metrics** for the pilot.
8. **M9/M10 — `papers/` literature review + paper draft**, citing only measured results.

### Deviations from the literal brief (flagged for approval)
- The brief says create `research/REPOSITORY_AUDIT.md` (**done — this file**) and a
  parallel `research/` + `papers/` tree. The repo already uses `docs/`. I recommend
  **keeping `docs/` as the home for architecture/experiments/limitations** and using
  `research/` + `papers/` only for the genuinely new artifacts (this audit, literature
  review, paper), to avoid fragmenting documentation. **Awaiting your decision.**
- Phases 2–3 (competition + dataset audit, literature review) are **partially done**
  inside `docs/` and the manifest; I'll extend rather than recreate them.

---

## 8. Integrity checklist (this phase)

- [x] Inspected before changing anything; no core file modified.
- [x] Ran existing tests (15 passed).
- [x] No fabricated results — all numbers cited come from `results/` / `docs/`.
- [x] No credentials or secrets found or added.
- [x] `grag_system` treated as read-only prior art; not touched.
- [x] Gemma 4 local inference **not** assumed — flagged as unverified (High risk).
