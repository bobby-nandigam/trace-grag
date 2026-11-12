"""
Gemma localizer — the Gemma 4 model as a bug-localization reasoner.

Given an issue and the top-K candidate symbols proposed by a retriever (E1/E2/E3),
the Gemma model picks the single symbol most likely to need the fix. This is the
agentic core of the pipeline reduced to one bounded, verifiable decision: it lets
us measure *whether better retrieval leads to better localization by the model*,
which is the question the competition cares about, without a full multi-turn agent
loop or a test-execution harness.

Design:
  * Backend is injected (``chat_fn``); default ``OllamaChat`` targets a local
    Gemma served by Ollama (``gemma4:e2b``). Stdlib-only, so tests inject a fake.
  * Deterministic decoding (temperature 0) for reproducibility.
  * The model is shown only the candidate list the retriever surfaced — never the
    gold patch or the hidden tests. The choice is parsed robustly; an unparseable
    answer is recorded as an abstention, never guessed into a hit.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Callable, Optional

from trace_grag.graph.schema import CodeNode

logger = logging.getLogger(__name__)

# A chat function maps a prompt to the model's text completion.
ChatFn = Callable[[str], str]

DEFAULT_MODEL = "gemma4:e2b"
DEFAULT_BASE_URL = "http://localhost:11434"


class ChatError(RuntimeError):
    """Raised when the generation backend cannot produce a completion."""


class OllamaChat:
    """Default generation backend: Ollama's ``/api/generate`` (non-streaming)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 120,
        temperature: float = 0.0,
        num_predict: int = 64,
        think: bool = False,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.num_predict = num_predict
        # Gemma 4 (E2B/E4B) is a reasoning model: with thinking on, its tokens go to
        # a separate `thinking` field and the answer may never fit the budget. For a
        # single bounded choice we disable thinking to get a direct, parseable answer.
        self.think = think

    def __call__(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": self.think,
            "options": {"temperature": self.temperature, "num_predict": self.num_predict},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as e:
            raise ChatError(
                f"could not reach generation backend at {self.base_url} "
                f"(model={self.model}): {e}. Is `ollama serve` running and the model pulled?"
            ) from e
        return data.get("response", "")


def _candidate_block(nodes: list[CodeNode], max_doc_chars: int = 240) -> str:
    lines = []
    for i, n in enumerate(nodes, start=1):
        sig = (n.signature or n.qualified_name)[:120]
        doc = (n.docstring or "").strip().replace("\n", " ")[:max_doc_chars]
        lines.append(f"{i}. {n.qualified_name} — {sig}" + (f"  // {doc}" if doc else ""))
    return "\n".join(lines)


def build_prompt(issue: str, candidates: list[CodeNode], max_issue_chars: int = 1500) -> str:
    return (
        "You are a software-engineering assistant. A bug report is given, followed by a "
        "numbered list of candidate functions/classes from the repository. Identify the ONE "
        "candidate most likely to contain the code that must be changed to fix the bug.\n\n"
        f"Bug report:\n{issue.strip()[:max_issue_chars]}\n\n"
        f"Candidates:\n{_candidate_block(candidates)}\n\n"
        "Answer with ONLY the number of the single most likely candidate (e.g. \"3\"). Number:"
    )


def parse_choice(text: str, n_candidates: int) -> Optional[int]:
    """Return a 1-based index in [1, n_candidates], or None if unparseable."""
    for m in re.finditer(r"\d+", text or ""):
        v = int(m.group())
        if 1 <= v <= n_candidates:
            return v
    return None


class GemmaLocalizer:
    def __init__(self, chat: Optional[ChatFn] = None, top_k: int = 10) -> None:
        self._chat: ChatFn = chat or OllamaChat()
        self.top_k = top_k

    def localize(self, issue: str, candidates: list[CodeNode]) -> dict:
        """Ask the model to pick the buggy symbol from ``candidates`` (already ranked).

        Returns a dict with the chosen node id (or None on abstention), the 1-based
        index, and the raw model text — so the caller can score and audit.
        """
        cands = candidates[: self.top_k]
        if not cands:
            return {"chosen_id": None, "choice": None, "raw": "", "n_candidates": 0}
        prompt = build_prompt(issue, cands)
        raw = self._chat(prompt)
        choice = parse_choice(raw, len(cands))
        chosen_id = cands[choice - 1].id if choice else None
        return {
            "chosen_id": chosen_id,
            "choice": choice,
            "raw": (raw or "")[:200],
            "n_candidates": len(cands),
        }
