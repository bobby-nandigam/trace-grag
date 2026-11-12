# TRACE-GRAG

**Test-Guided Repository Analysis and Graph-based Evidence Retrieval for Software Engineering Agents**

Repository-level bug localization and patch generation for resource-constrained,
locally-deployed **Gemma 4 (E2B/E4B)** software-engineering agents. TRACE-GRAG builds
a structured code graph of a repository, ranks evidence with lexical + semantic +
**test** + graph signals, and selects a token-budgeted connected subgraph as agent
context.

> Research prototype for the Google *Gemma 4 Developer Agent* Paper Track.
> Built to run on a 16 GB Apple-Silicon Mac. Results are reported honestly, including
> negative and inconclusive findings — see [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

## Install

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .            # core
pip install -e ".[eval]"    # pandas/sklearn/matplotlib for analysis
```

## Quickstart — index a repo and localize an issue

```bash
# 1. Build the benchmark manifest from SWE-bench Lite (24 pinned tasks, 10 repos)
python scripts/build_manifest.py

# 2. Run bug localization (Tier A) on two small repos
python scripts/run_localization.py --repos psf/requests pallets/flask

# 3. Aggregate with bootstrap confidence intervals
python scripts/evaluate.py
```

Try the graph on the bundled synthetic fixture (no download needed):

```python
from trace_grag import PythonParser, RepoGraph
nodes, edges = PythonParser("data/sample/minirepo", repo_name="minirepo").parse()
g = RepoGraph("minirepo"); g.add_nodes(nodes); g.add_edges(edges)
print(g.stats())                       # node/edge counts by type
print(g.search_symbols("divide"))      # symbol search (an agent tool)
```

## Status

| Component | State |
|---|---|
| Code graph (6 node + 6 edge types, provenance + confidence) | ✅ |
| Disk-safe repo snapshots | ✅ |
| BM25 (E1) + static graph (E3) retrieval | ✅ |
| Localization metrics (Recall/hit@k, MRR, bootstrap CIs) | ✅ |
| Semantic (E2), test-guided (E4), combined ranker, compression (E5) | ⏳ |
| Gemma E2B agent + bounded repair + Tier-B execution pilot | ⏳ |

## Design

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline and schema
- [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) — results (with CIs)
- [`docs/EXISTING_GRAG_AUDIT.md`](docs/EXISTING_GRAG_AUDIT.md) — relation to the prior GRAG project
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — hardware constraints and honest scope

## License

Apache-2.0.
