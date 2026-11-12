# Limitations & Honest Scope (living document)

This file records constraints and the design decisions forced by them, so the paper
can report scope honestly rather than overclaim.

## Hardware (measured 2026-11-07)

- Mac mini **M4, 16 GB** unified memory, macOS 26.3.1, arm64, 10 cores.
- **~21 GB free disk** (460 GB volume, 96% full). **This is the binding constraint.**
- Runtimes present: Ollama 0.18.2 (daemon OK), Docker 29.3.1 + Colima, no `gemma4`
  pulled yet; `nomic-embed-text` already local (used for the semantic baseline).

## Consequences

1. **No standard SWE-bench Docker evaluation harness.** The official per-task images
   total well over 100 GB — infeasible on 21 GB free. **Decision:** evaluate in two
   tiers (see `EXPERIMENTS.md`):
   - **Tier A — Bug localization (primary, rigorous):** needs only a shallow repo
     checkout at the pinned commit + the gold patch's changed-file/function list.
     Metrics: Recall@5/@10, MRR. No execution, so it runs for the full task set and
     carries the main statistical claims. This is where retrieval quality (E1–E5,
     ablations) is measured.
   - **Tier B — Patch execution (pilot, small N):** 3–5 tasks whose environments
     install cheaply into a per-repo venv (not Docker), to demonstrate the
     end-to-end Gemma agent (apply patch → run tests). Reported explicitly as a
     **pilot**, never generalized to a full SWE-bench score.

2. **Model: Gemma 4 E2B primary, E4B if memory permits.** Matches the competition's
   mandated base models (E2B/E4B) and the 16 GB budget. Exactly one model/quant is
   fixed across all conditions. `gemma4` requires an Ollama upgrade (0.18→≥0.22) —
   to be verified on Day 4 before the agent stage.

3. **Python-only graph** for the pipeline (built-in `ast`). JS/TS via Tree-sitter is
   documented as future work; SWE-bench Lite is Python-only, so this is sufficient.

## Known open items (to verify, not assume)

- Exact Kaggle **Paper Track** submission format/page-limit/licensing — the page is
  JS-rendered and needs the user's logged-in access; tracked in the submission checklist.
- Whether Ollama 0.18.2 can serve `gemma4` or needs upgrading.
- Coverage-based COVERS edges depend on Tier-B execution and so exist only for pilot tasks.
