# Related Work

Scope: retrieval and graph methods for **repository-level** code understanding and
autonomous software engineering, with emphasis on **bug localization** (the task this
work measures). Full citations in `REFERENCES.md`.

## 1. Autonomous SE agents and the localize-then-repair pattern

SWE-bench [2] established the task of resolving real GitHub issues against a hidden test
suite, and SWE-agent [3] showed that a tool-using LLM with an agent–computer interface can
attempt it end to end. **Agentless** [1] then demonstrated that a *simple, non-agentic*
pipeline — hierarchical **localization** (file → class/function → edit) followed by
repair — is competitive with or better than agent loops at a fraction of the cost, and
that localization combining LLM reasoning with classic information retrieval is central to
performance. This motivates our focus on **localization as a measurable sub-problem** that
can be studied rigorously without a full execution harness.

## 2. Code graphs for software engineering

Code Property Graphs [5] unified AST, control-flow, and program-dependence information
into a single queryable structure for vulnerability discovery. In the LLM era,
**RepoGraph** [4] builds a repository-level graph whose **nodes are individual lines of
code** and whose **edges capture definition/reference dependencies**, and plugs it into
four SWE-bench systems to improve them. RepoGraph is the **closest prior art** to this
work: both use a repository graph to steer retrieval for issue resolution.

## 3. Retrieval for code

Classic lexical retrieval (BM25 [11]) and dense retrieval (DPR [10], Sentence-BERT [12],
and modern long-context embedders such as nomic-embed [13]) are the two standard families.
RepoCoder [6] showed iterative retrieval-generation for repository-level completion.
General RAG [8] and **Graph RAG** [9] fuse a knowledge graph with vector retrieval for
question answering — the natural-language ancestor of code-graph retrieval, and the design
pattern the authors' prior `grag_system` project implemented for NL QA.

## 4. Where this work sits

Prior graph-for-SE work (esp. RepoGraph [4]) establishes that repository graphs help.
**This work does not claim that as novel.** It instead asks a narrower, measurable
question the prior work does not isolate: **under tight local-inference constraints
(a 16 GB Apple-Silicon machine, Gemma-class models, no Docker execution harness), how do
lexical, semantic, and graph retrieval actually compare for bug localization, and does
graph expansion add value over a strong lexical baseline?** We report this comparison with
confidence intervals, including where graph retrieval does **not** help — a negative/neutral
result that the "graphs help" literature does not foreground. See `RESEARCH_GAP.md`.
