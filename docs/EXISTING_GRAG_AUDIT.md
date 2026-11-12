# Existing GRAG Audit

**Audited repository:** https://github.com/bobby-nandigam/grag_system (MIT, v1.1.0, ~2,680 LOC Python)
**Audit date:** 2026-11-07
**Purpose:** Establish exactly what TRACE-GRAG inherits from GRAG and what is genuinely new, so no existing GRAG capability is re-claimed as a TRACE-GRAG research contribution.

## 1. What GRAG is

GRAG is a **natural-language GraphRAG system for question answering**. Its knowledge
graph stores `(subject, predicate, object)` triples *mined from prose* (e.g.
`python --[created_by]--> guido van rossum`). Retrieval combines dense vector
similarity with a graph-neighbor score boost, and a multi-stage pipeline adds
reasoning, self-critique, and RL-based weight adaptation.

### Architecture (from `grag/`)

| Module | Role |
|---|---|
| `core/pipeline.py` | 11-stage orchestrator: parse → retrieve → reason → generate → critic → refine → RL → memory |
| `core/models.py` | Dataclasses: `Triple`, `RetrievedDocument`, `GraphPath`, `FusedContext`, `GRAGAnswer` |
| `core/config.py` | `GRAGConfig` dataclass (`top_k`, `max_hops`, `graph_weight`+`vector_weight`=1.0, …) |
| `graph/knowledge_graph.py` | NetworkX `MultiDiGraph` of NL triples; `find_paths`, `get_neighbors`, `extract_subgraph`; JSON persistence as a flat triple list |
| `extraction/relation_extractor.py` | spaCy-or-regex extraction of triples from text |
| `retrieval/hybrid_retriever.py` | `VectorStore` (sentence-transformers / TF-IDF fallback) + graph-neighbor boost (+0.05/match) |
| `retrieval/query_understanding.py` | intent / entity / relationship parsing of the question |
| `reasoning/graph_reasoner.py` | entity linking, multi-hop traversal, path ranking, contradiction detection |
| `evaluation/critic.py` | faithfulness/relevance/completeness/consistency self-scoring |
| `rl/reward_engine.py` | per-pattern reward; adapts `top_k`, `max_hops`, weights |
| `memory/memory_store.py` | episodic cache of successful/failed query patterns |

## 2. Reusable components / patterns (inherited by TRACE-GRAG)

These are **engineering patterns** carried over — explicitly credited, not claimed as novel:

1. **Graph store pattern** — NetworkX `MultiDiGraph`, per-edge `confidence`/`source`
   metadata, `get_neighbors`, `extract_subgraph`, and **version-independent JSON
   persistence as a flat node/edge list**. TRACE-GRAG's `graph/repo_graph.py` mirrors
   this directly, with a code-symbol schema instead of NL triples.
2. **Hybrid multi-signal retrieval** — GRAG fuses a lexical/semantic score with a
   graph signal. This is the direct ancestor of TRACE-GRAG's ranking
   `S(v,q)=αL+βE+γT+δG`. GRAG implements `L`/`E` (vector) and a crude `G`
   (neighbor boost); TRACE-GRAG adds a normalized combination plus the new `T`
   (test evidence) term.
3. **Provenance + confidence on every edge** — GRAG records `source`, `confidence`,
   `recency`. TRACE-GRAG keeps this discipline and extends it with a `Provenance`
   enum (`ast_static`, `call_resolved`, `name_heuristic`, `coverage_dynamic`,
   `unresolved`).
4. **Subgraph extraction** — GRAG's `extract_subgraph(entities, max_hops)` is the
   ancestor of TRACE-GRAG's *budget-aware connected-subgraph* context selection.
5. **Abstention / safety** — GRAG returns "Insufficient evidence" rather than
   fabricating. TRACE-GRAG keeps this stance for retrieval and patching.
6. **Config-dataclass + tunable weights** discipline.

## 3. GRAG limitations relative to a repository SE agent

GRAG has **no code awareness whatsoever**:

- No source parsing (no AST, no Tree-sitter). Its "entities" are NL noun phrases,
  not code symbols; it has no notion of a file, function, class, import, or call.
- No source locations, line ranges, or content hashes for symbols.
- No tests: no test discovery, no test→code links, no coverage, no execution.
- No token-budget context compression for an LLM context window.
- No issue-conditioned retrieval, no bug localization, no patch generation, no
  tool-using agent, no sandboxed execution, no localization/patch metrics.
- The RL reward engine, critic, memory store, query-understanding and
  contradiction-detection are **Q&A-specific** and largely irrelevant to repo SE;
  TRACE-GRAG deliberately does **not** carry them over rather than force a fit.

## 4. New TRACE-GRAG capabilities (the genuine contributions)

| Capability | In GRAG? | TRACE-GRAG |
|---|---|---|
| Code-symbol graph (FILE/MODULE/CLASS/FUNCTION/METHOD/TEST) | ✗ | ✓ `ast`-based parser, 6 node + 6 edge types with line-precise locations |
| Static relationships (CONTAINS/DEFINES/IMPORTS/CALLS/TESTS) | ✗ | ✓ with explicit `UNRESOLVED` marking (never invented) |
| **Issue-conditioned** retrieval over a repo | ✗ | ✓ (Contribution 1) |
| **Test-guided** evidence ranking (`T` term, COVERS from coverage) | ✗ | ✓ (Contribution 2) |
| **Budget-aware** connected-subgraph context selection | partial (`extract_subgraph`, not budgeted) | ✓ token-budgeted (Contribution 3) |
| Gemma 4 (E2B/E4B) local SE agent with tools + bounded repair | ✗ | ✓ |
| Bug-localization (Recall@k) + patch metrics | ✗ | ✓ |

## 5. Independence & integrity rules honored

- The original `grag_system` repository is **left unchanged** (audited from a
  read-only clone in a scratch directory).
- Reused ideas are documented here and credited in code module docstrings.
- "Using a graph for repository understanding" is **not** claimed as novel (see
  `RELATED_WORK.md`: RepoGraph and others). The claimed novelty is the *specific
  combination* of issue-conditioning + test-guided ranking + budget-aware
  subgraph selection under local E2B/E4B inference.
