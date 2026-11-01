"""Metrics for binary/graded reranking evaluation (MTEB-style)."""
import math


def ndcg(ranked_rels, k=10):
    """ranked_rels: relevance grades in ranked order (pool grades appended for IDCG)."""
    d = sum(r / math.log2(i + 2) for i, r in enumerate(ranked_rels[:k]) if r > 0)
    ideal = sorted(ranked_rels, reverse=True)
    id_ = sum(r / math.log2(i + 2) for i, r in enumerate(ideal[:k]) if r > 0)
    return d / id_ if id_ > 0 else 0.0


def average_precision(ranked_rels):
    hits = 0
    s = 0.0
    for i, r in enumerate(ranked_rels):
        if r > 0:
            hits += 1
            s += hits / (i + 1)
    total = sum(1 for r in ranked_rels if r > 0)
    return s / total if total else 0.0


def mrr(ranked_rels, k=10):
    for i, r in enumerate(ranked_rels[:k]):
        if r > 0:
            return 1.0 / (i + 1)
    return 0.0


def recall(ranked_rels, k=10):
    total = sum(1 for r in ranked_rels if r > 0)
    if total == 0:
        return 0.0
    return sum(1 for r in ranked_rels[:k] if r > 0) / total


METRICS = ("ndcg@5", "ndcg@10", "map", "mrr@10", "recall@10", "hit@1")


def score_ranking(ranked_rels):
    return {
        "ndcg@5": ndcg(ranked_rels, 5),
        "ndcg@10": ndcg(ranked_rels, 10),
        "map": average_precision(ranked_rels),
        "mrr@10": mrr(ranked_rels, 10),
        "recall@10": recall(ranked_rels, 10),
        "hit@1": 1.0 if ranked_rels and ranked_rels[0] > 0 else 0.0,
    }
