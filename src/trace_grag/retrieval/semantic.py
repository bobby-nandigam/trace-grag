"""
Semantic (dense) retrieval — E2 baseline.

Embeds each candidate symbol's ``node_document`` and the issue text with a local
embedding model (default: ``nomic-embed-text`` served by Ollama), then ranks
candidates by cosine similarity. This is the conventional **vector retrieval**
baseline the research question compares graph/dependency-aware retrieval against.

Design choices (consistent with the rest of the package):
  * Implements the ``Retriever`` protocol (``name`` + ``rank``) — a drop-in
    alongside ``BM25Retriever`` (E1) and ``GraphRetriever`` (E3). No existing
    module is modified.
  * The embedding backend is **injected** (``embedder`` callable). The default
    ``OllamaEmbedder`` uses only the standard library (``urllib``), so no new
    dependency is added; tests inject a deterministic fake embedder and therefore
    never require a running Ollama server.
  * Embeddings are cached by the node's ``source_hash`` so re-indexing an
    unchanged symbol is free and runs are reproducible.
  * Never fabricates: if the backend is unreachable, the default embedder raises a
    clear ``EmbeddingError`` rather than returning zeros that would silently skew
    similarity.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

import numpy as np

from trace_grag.graph.repo_graph import RepoGraph
from trace_grag.graph.schema import CodeNode
from trace_grag.retrieval.base import candidate_nodes, node_document

logger = logging.getLogger(__name__)

# An embedder maps a batch of texts to a list of equal-length float vectors.
EmbedFn = Callable[[list[str]], list[list[float]]]

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_BASE_URL = "http://localhost:11434"


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend cannot produce an embedding."""


class OllamaEmbedder:
    """Default embedding backend: Ollama's batched ``/api/embed`` endpoint.

    Embeds a whole batch in one request (far fewer round-trips than one-per-text,
    which both speeds up large repos and avoids the transient HTTP 500s seen when
    the server is hammered with thousands of tiny requests). Transient 5xx and
    connection errors are retried with exponential backoff; a persistent failure
    raises ``EmbeddingError`` rather than returning zeros. Stdlib-only.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 120,
        max_retries: int = 4,
        backoff_base: float = 1.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.backoff_base = backoff_base

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                embs = data.get("embeddings")
                if not embs or len(embs) != len(texts):
                    raise EmbeddingError(
                        f"backend returned {len(embs) if embs else 0} embeddings "
                        f"for {len(texts)} inputs (model={self.model})"
                    )
                return [[float(x) for x in v] for v in embs]
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code < 500:  # client error — retrying won't help
                    raise EmbeddingError(
                        f"embedding backend rejected request (HTTP {e.code}, "
                        f"model={self.model}): {e}"
                    ) from e
                # 5xx: transient, fall through to backoff
            except (urllib.error.URLError, OSError, EmbeddingError) as e:
                last_err = e
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff_base * (2 ** attempt))
        raise EmbeddingError(
            f"could not get embeddings from {self.base_url} after "
            f"{self.max_retries} attempts (model={self.model}): {last_err}. "
            f"Is `ollama serve` running and the model pulled?"
        )


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0  # avoid division by zero for empty docs
    return mat / norms


class SemanticRetriever:
    """E2 dense retrieval over candidate symbols (FUNCTION/METHOD/CLASS)."""

    name = "semantic"

    def __init__(
        self,
        embedder: Optional[EmbedFn] = None,
        batch_size: int = 32,
        max_doc_chars: int = 4000,
    ) -> None:
        self._embedder: EmbedFn = embedder or OllamaEmbedder()
        self.batch_size = max(1, batch_size)
        # Truncate each document to stay under the embedder's context window.
        # A single over-long input (e.g. a giant class docstring) otherwise makes
        # the batched /api/embed endpoint reject the whole batch with HTTP 400
        # ("input length exceeds the context length"). The high-signal head
        # (qualified name, signature, docstring start) is preserved.
        self.max_doc_chars = max(256, max_doc_chars)
        self._ids: list[str] = []
        self._matrix: Optional[np.ndarray] = None       # (n_candidates, dim), L2-normalized
        self._cache: dict[str, list[float]] = {}        # source_hash -> embedding

    # ── indexing ──────────────────────────────────────────────────────────────
    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._embedder(texts[i : i + self.batch_size]))
        return out

    def index(self, graph: RepoGraph) -> None:
        cands: list[CodeNode] = candidate_nodes(graph)
        self._ids = [n.id for n in cands]
        if not cands:
            self._matrix = None
            return

        # Resolve from cache where possible (keyed by content hash); embed the rest.
        to_embed: list[str] = []
        to_embed_idx: list[int] = []
        vectors: list[Optional[list[float]]] = [None] * len(cands)
        for i, n in enumerate(cands):
            key = n.source_hash
            if key and key in self._cache:
                vectors[i] = self._cache[key]
            else:
                to_embed.append(node_document(n)[: self.max_doc_chars])
                to_embed_idx.append(i)

        if to_embed:
            logger.info("semantic: embedding %d/%d candidate symbols (rest cached)",
                        len(to_embed), len(cands))
            fresh = self._embed_texts(to_embed)
            for j, vec in zip(to_embed_idx, fresh):
                vectors[j] = vec
                h = cands[j].source_hash
                if h:
                    self._cache[h] = vec

        self._matrix = _l2_normalize(np.asarray(vectors, dtype=np.float64))

    # ── ranking ───────────────────────────────────────────────────────────────
    def rank(self, issue: str, graph: RepoGraph) -> list[tuple[str, float]]:
        if self._matrix is None or not self._ids:
            self.index(graph)
        if self._matrix is None or not self._ids:
            return []
        q = self._embedder([issue[: self.max_doc_chars]])[0]
        qv = np.asarray(q, dtype=np.float64)
        qn = np.linalg.norm(qv)
        if qn == 0.0 or math.isnan(qn):
            return []
        qv = qv / qn
        sims = self._matrix @ qv  # cosine (both sides L2-normalized)
        order = np.argsort(-sims)
        return [(self._ids[i], float(sims[i])) for i in order]
