# References

**Verification status legend:**
- `[VERIFIED]` — title/authors/venue confirmed via web search during this project (2026-11-12).
- `[WELL-ESTABLISHED]` — widely-cited work; high confidence, but **confirm the exact
  venue/year/arXiv id against the source before final submission**.
- `[CONFIRM]` — used because it is directly relevant, but a detail (year, arXiv id, or
  exact author list) is **not** independently confirmed this session; the author must
  verify before citing in the submitted paper.

No citation below was invented. Where a detail is uncertain it is marked, not guessed.

---

### Benchmarks & agentic SE

1. **[VERIFIED]** Xia, C. S., Deng, Y., Dunn, S., Zhang, L. *Agentless: Demystifying
   LLM-based Software Engineering Agents.* arXiv:2407.01489 (2024); FSE 2025.
   Two-phase **localize-then-repair**; hierarchical localization (file → class/function →
   edit) combining LLM- and IR-based localization. Code: github.com/OpenAutoCoder/Agentless.
2. **[WELL-ESTABLISHED]** Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K.,
   Press, O., Narasimhan, K. *SWE-bench: Can Language Models Resolve Real-World GitHub
   Issues?* ICLR 2024. arXiv:2310.06770. (Benchmark; SWE-bench Lite is the subset used here.)
3. **[WELL-ESTABLISHED]** Yang, J., Jimenez, C. E., Wettig, A., et al. *SWE-agent:
   Agent-Computer Interfaces Enable Automated Software Engineering.* NeurIPS 2024.
   arXiv:2405.15793.

### Code graphs & repository-level retrieval

4. **[VERIFIED]** Ouyang, S., Yu, W., Ma, K., Xiao, Z., Zhang, Z., Jia, M., Han, J.,
   Zhang, H., Yu, D. *RepoGraph: Enhancing AI Software Engineering with Repository-level
   Code Graph.* ICLR 2025. arXiv:2410.14684. Graph nodes = lines of code; edges = code
   definition/reference dependencies. Code: github.com/ozyyshr/RepoGraph.
   **Closest prior art** to this work (see `RESEARCH_GAP.md`).
5. **[WELL-ESTABLISHED]** Yamaguchi, F., Golde, N., Arp, D., Rieck, K. *Modeling and
   Discovering Vulnerabilities with Code Property Graphs.* IEEE S&P 2014. (Origin of the
   code-property-graph idea that unifies AST/CFG/PDG.)
6. **[CONFIRM]** Zhang, F., Chen, B., Zhang, Y., et al. *RepoCoder: Repository-Level Code
   Completion Through Iterative Retrieval and Generation.* EMNLP 2023. arXiv:2303.12570.
7. **[CONFIRM]** Ding, Y., et al. *CrossCodeEval: A Diverse and Multilingual Benchmark for
   Cross-File Code Completion.* NeurIPS 2023. (Used by RepoGraph for transferability.)

### Retrieval-augmented generation & graph RAG

8. **[WELL-ESTABLISHED]** Lewis, P., Perez, E., Piktus, A., et al. *Retrieval-Augmented
   Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. arXiv:2005.11401.
9. **[WELL-ESTABLISHED]** Edge, D., Trinh, H., Cheng, N., et al. *From Local to Global:
   A Graph RAG Approach to Query-Focused Summarization.* arXiv:2404.16130 (2024).
10. **[WELL-ESTABLISHED]** Karpukhin, V., Oğuz, B., Min, S., et al. *Dense Passage
    Retrieval for Open-Domain Question Answering.* EMNLP 2020. arXiv:2004.04906.

### Retrieval scoring & embeddings

11. **[WELL-ESTABLISHED]** Robertson, S., Zaragoza, H. *The Probabilistic Relevance
    Framework: BM25 and Beyond.* Foundations and Trends in Information Retrieval, 2009.
12. **[WELL-ESTABLISHED]** Reimers, N., Gurevych, I. *Sentence-BERT: Sentence Embeddings
    using Siamese BERT-Networks.* EMNLP 2019. arXiv:1908.10084.
13. **[CONFIRM]** Nussbaum, Z., Morris, J. X., Duderstadt, B., Mulyar, A. *Nomic Embed:
    Training a Reproducible Long Context Text Embedder.* arXiv:2402.01613 (2024).
    (The `nomic-embed-text` model used for E2 semantic retrieval.)

### Models

14. **[CONFIRM]** Gemma Team, Google DeepMind. *Gemma 4 Technical Report.* (2026). The
    competition-provided base model family (E2B/E4B). **The exact report title / arXiv id
    must be taken from the official competition materials before submission** — do not cite
    a guessed identifier.
15. **[WELL-ESTABLISHED]** Gemma Team, Google DeepMind. *Gemma 2: Improving Open Language
    Models at a Practical Size.* arXiv:2408.00118 (2024). (Prior Gemma generation, for
    background on the open-weights lineage.)

---

**Action for the author before submission:** resolve every `[CONFIRM]` and the Gemma 4
report identifier (#14) against primary sources (arXiv / the Kaggle competition page).
Remove any reference the final text does not actually cite.
