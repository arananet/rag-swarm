"""Multi-stage re-ranker — addresses single-stage retrieval failures.

Implements the multi-stage retrieval pattern from Mixpeek's architecture:
1. Broad recall from swarm agents (embedding search)
2. Re-ranking with cross-encoder (BGE reranker via Cloudflare Workers AI)
3. Deduplication of near-identical chunks

This directly addresses the Karpathy "complexity ceiling" criticism by
ensuring retrieval quality scales with precision, not just recall.
"""

from __future__ import annotations

from app.embeddings import rerank_pairs
from app.models.schemas import RetrievalResult


def rerank_results(
    query: str,
    results: list[RetrievalResult],
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Re-rank results using Cloudflare BGE reranker for cross-encoder precision.

    Cross-encoders attend to fine-grained interactions between query and document
    that bi-encoders miss. This consistently improves precision 15-30% on benchmarks.
    """
    if not results:
        return []

    passages = [r.content for r in results]
    scores = rerank_pairs(query, passages)

    # Update scores with reranker output
    reranked: list[RetrievalResult] = []
    for result, rerank_score in zip(results, scores):
        reranked.append(
            RetrievalResult(
                chunk_id=result.chunk_id,
                content=result.content,
                modality=result.modality,
                score=rerank_score,
                metadata={**result.metadata, "original_score": result.score},
                agent=result.agent,
            )
        )

    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked[:top_k]


def deduplicate_results(
    results: list[RetrievalResult],
    similarity_threshold: float = 0.92,
) -> list[RetrievalResult]:
    """Remove near-duplicate results based on content overlap.

    Common when the same content appears via overlapping chunks or when
    multiple agents retrieve variants of the same document section.
    """
    if len(results) <= 1:
        return results

    unique: list[RetrievalResult] = [results[0]]
    for candidate in results[1:]:
        is_dup = False
        for kept in unique:
            overlap = _content_overlap(candidate.content, kept.content)
            if overlap >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(candidate)

    return unique


def _content_overlap(a: str, b: str) -> float:
    """Compute Jaccard similarity between two text strings (word-level)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
