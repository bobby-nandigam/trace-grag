# TRACE-GRAG Architecture

```
issue (problem_statement)
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Stage 1  Ingestion      snapshot at pinned commit (disk-safe tarball) │
│ Stage 2  Parsing+Graph  ast → CodeNodes/CodeEdges → RepoGraph         │
│ Stage 3  Retrieval      E1 BM25 · E2 semantic · E3 graph · E4 +test   │
│ Stage 4  Ranking        S(v,q)=αL+βE+γT+δG  (normalized, dev-tuned)   │
│ Stage 5  Compression    budget-aware connected-subgraph selection     │
│ Stage 6  Agent          Gemma E2B/E4B + tools + bounded repair loop   │
│ Stage 7  Execution      per-repo venv sandbox (Tier-B pilot)          │
└─────────────────────────────────────────────────────────────────────┘
        │                                   │
        ▼                                   ▼
  localization metrics (Tier A)       patch success (Tier B pilot)
```

## Graph schema (`graph/schema.py`)

- **Nodes:** FILE, MODULE, CLASS, FUNCTION, METHOD, TEST — each with a stable id,
  repo-relative path, line range, content hash, signature, docstring.
- **Edges:** CONTAINS, DEFINES, IMPORTS, CALLS, TESTS, COVERS — each with a
  `Provenance` (`ast_static`, `call_resolved`, `name_heuristic`,
  `coverage_dynamic`, `unresolved`) and a confidence. Unresolvable targets are
  recorded as `unresolved`, never invented.

## Components

| Stage | Module | Status |
|---|---|---|
| Ingestion | `ingestion/snapshot.py` | ✅ tarball fetch + safe extract + cleanup |
| Parsing | `parsing/python_parser.py` | ✅ `ast` two-pass (Python); Tree-sitter = future (JS/TS) |
| Graph | `graph/repo_graph.py` | ✅ NetworkX store, neighbors, subgraph, JSON persist |
| Retrieval | `retrieval/{lexical,graph_retrieval}.py` | ✅ E1, E3 · ⏳ E2 semantic, E4 test |
| Ranking | `ranking/` | ⏳ combined S(v,q) |
| Compression | `compression/` | ⏳ budget-aware subgraph |
| Agent | `agent/` | ⏳ Gemma E2B tools + repair loop |
| Evaluation | `evaluation/{localization,metrics}.py` | ✅ Recall/hit/MRR + bootstrap CIs |

## Why `ast` not Tree-sitter (yet)

SWE-bench Lite is Python-only, and the standard-library `ast` is precise,
version-matched, and dependency-free. Tree-sitter remains the documented path for
adding JavaScript/TypeScript later; the parser interface returns plain
`CodeNode`/`CodeEdge` lists so a Tree-sitter backend can be dropped in without
touching the graph or retrieval layers.
