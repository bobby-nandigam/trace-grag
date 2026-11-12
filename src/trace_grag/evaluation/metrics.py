"""Bug-localization metrics."""
from __future__ import annotations


def hit_at_k(ranked_ids: list[str], gold: set[str], k: int) -> float:
    """1.0 if any gold symbol appears in the top-k, else 0.0."""
    return 1.0 if gold & set(ranked_ids[:k]) else 0.0


def recall_at_k(ranked_ids: list[str], gold: set[str], k: int) -> float:
    """Fraction of gold symbols appearing in the top-k."""
    if not gold:
        return 0.0
    return len(gold & set(ranked_ids[:k])) / len(gold)


def mrr(ranked_ids: list[str], gold: set[str]) -> float:
    """Reciprocal rank of the first gold symbol (0 if none retrieved)."""
    for i, nid in enumerate(ranked_ids, start=1):
        if nid in gold:
            return 1.0 / i
    return 0.0


def score_ranking(ranked_ids: list[str], gold: set[str], ks=(1, 5, 10)) -> dict:
    out: dict[str, float] = {"mrr": mrr(ranked_ids, gold), "n_gold": len(gold)}
    for k in ks:
        out[f"hit@{k}"] = hit_at_k(ranked_ids, gold, k)
        out[f"recall@{k}"] = recall_at_k(ranked_ids, gold, k)
    return out
