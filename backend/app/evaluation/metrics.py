"""Evaluation metrics — precision, recall, NDCG, MRR for comparing retrieval approaches."""

from __future__ import annotations

import math

import numpy as np

from app.models.schemas import EvaluationMetrics, OracleVerdict, RetrievalResult


def compute_metrics(
    results: list[RetrievalResult],
    verdicts: list[OracleVerdict] | None = None,
    threshold: float = 0.3,
) -> EvaluationMetrics:
    """Compute IR metrics using oracle verdicts as relevance judgments.
    
    If no verdicts are provided, uses the result scores against the threshold.
    """
    if not results:
        return EvaluationMetrics(
            precision=0.0, recall=0.0, ndcg=0.0, mrr=0.0, avg_relevance=0.0
        )

    # Build relevance labels: 1 if passed oracle / above threshold, 0 otherwise
    if verdicts:
        verdict_map = {v.chunk_id: v for v in verdicts}
        relevance = [
            1.0 if verdict_map.get(r.chunk_id, OracleVerdict(
                chunk_id=r.chunk_id, relevance_score=0, reasoning="", passed=False
            )).passed else 0.0
            for r in results
        ]
        scores = [
            verdict_map.get(r.chunk_id, OracleVerdict(
                chunk_id=r.chunk_id, relevance_score=0, reasoning="", passed=False
            )).relevance_score
            for r in results
        ]
    else:
        relevance = [1.0 if r.score >= threshold else 0.0 for r in results]
        scores = [r.score for r in results]

    # Precision: fraction of retrieved results that are relevant
    relevant_count = sum(relevance)
    precision = relevant_count / len(results) if results else 0.0

    # Recall: we use relevant_count / max(relevant_count, 1) since we don't have
    # full corpus relevance judgments — this is recall@k
    # In a real system, ground truth would provide the denominator
    total_possible_relevant = max(relevant_count, 1.0)
    recall = relevant_count / total_possible_relevant

    # NDCG (Normalized Discounted Cumulative Gain)
    ndcg = _compute_ndcg(scores)

    # MRR (Mean Reciprocal Rank)
    mrr = _compute_mrr(relevance)

    # Average relevance score
    avg_relevance = float(np.mean(scores)) if scores else 0.0

    return EvaluationMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        ndcg=round(ndcg, 4),
        mrr=round(mrr, 4),
        avg_relevance=round(avg_relevance, 4),
    )


def _compute_ndcg(scores: list[float], k: int | None = None) -> float:
    """Compute NDCG@k."""
    if not scores:
        return 0.0
    if k is not None:
        scores = scores[:k]

    dcg = sum(s / math.log2(i + 2) for i, s in enumerate(scores))
    ideal_scores = sorted(scores, reverse=True)
    idcg = sum(s / math.log2(i + 2) for i, s in enumerate(ideal_scores))

    return dcg / idcg if idcg > 0 else 0.0


def _compute_mrr(relevance: list[float]) -> float:
    """Compute Mean Reciprocal Rank."""
    for i, rel in enumerate(relevance):
        if rel > 0:
            return 1.0 / (i + 1)
    return 0.0


def compute_improvement(
    swarm_metrics: EvaluationMetrics,
    traditional_metrics: EvaluationMetrics,
) -> dict[str, float]:
    """Compute percentage improvement of swarm over traditional."""

    def _pct(swarm_val: float, trad_val: float) -> float:
        if trad_val == 0:
            return 100.0 if swarm_val > 0 else 0.0
        return round(((swarm_val - trad_val) / trad_val) * 100, 2)

    return {
        "precision_pct": _pct(swarm_metrics.precision, traditional_metrics.precision),
        "recall_pct": _pct(swarm_metrics.recall, traditional_metrics.recall),
        "ndcg_pct": _pct(swarm_metrics.ndcg, traditional_metrics.ndcg),
        "mrr_pct": _pct(swarm_metrics.mrr, traditional_metrics.mrr),
        "avg_relevance_pct": _pct(
            swarm_metrics.avg_relevance, traditional_metrics.avg_relevance
        ),
    }
