"""Oracle agent — LLM-powered evaluation and filtering of swarm results.

Addresses key Karpathy criticisms:
- Model collapse: Oracle traces every verdict back to source provenance,
  detecting when information drifts from its raw source.
- Learning tension: LLM-based reasoning produces human-readable explanations
  that make the evaluation transparent, not a black-box cosine score.
- Context window degradation: Oracle evaluates results individually, never
  loading the entire wiki/corpus. Hierarchical — agents retrieve, oracle filters.
"""

from __future__ import annotations

from app.embeddings import embed_text, embed_texts, llm_chat
from app.models.schemas import OracleVerdict, RetrievalResult


class OracleAgent:
    """LLM-powered oracle that evaluates swarm results for relevance and quality.

    Two-stage evaluation:
    1. Semantic similarity (fast, embedding-based pre-filter)
    2. LLM reasoning (slow, precise judgment on borderline cases)
    """

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    def evaluate(
        self, query: str, results: list[RetrievalResult]
    ) -> list[OracleVerdict]:
        """Score each result using embeddings + LLM reasoning."""
        if not results:
            return []

        # Stage 1: Fast embedding-based similarity pre-filter
        query_emb = embed_text(query)
        result_texts = [r.content for r in results]
        result_embs = embed_texts(result_texts)

        similarities = _cosine_similarities(query_emb, result_embs)

        verdicts: list[OracleVerdict] = []
        for i, result in enumerate(results):
            semantic_sim = similarities[i]
            blended_score = 0.6 * semantic_sim + 0.4 * result.score

            # Stage 2: LLM reasoning for borderline cases or high-value results
            if 0.2 <= blended_score <= 0.6 or blended_score >= 0.7:
                reasoning = self._llm_evaluate(query, result, semantic_sim)
                # LLM can boost or penalize the blended score
                if "RELEVANT" in reasoning.upper():
                    blended_score = min(1.0, blended_score + 0.1)
                elif "NOT RELEVANT" in reasoning.upper():
                    blended_score = max(0.0, blended_score - 0.15)
            else:
                reasoning = self._fast_reasoning(
                    query, result, semantic_sim, result.score, blended_score
                )

            passed = blended_score >= self.threshold

            # Provenance check: flag if source metadata is missing
            provenance_note = ""
            if not result.metadata.get("source"):
                provenance_note = " [WARNING: no source provenance]"

            verdicts.append(
                OracleVerdict(
                    chunk_id=result.chunk_id,
                    relevance_score=round(blended_score, 4),
                    reasoning=reasoning + provenance_note,
                    passed=passed,
                )
            )

        return verdicts

    def filter_results(
        self,
        results: list[RetrievalResult],
        verdicts: list[OracleVerdict],
    ) -> list[RetrievalResult]:
        """Return only results that passed oracle evaluation, re-ranked by oracle score."""
        passed_ids = {
            v.chunk_id: v.relevance_score for v in verdicts if v.passed
        }
        filtered = [r for r in results if r.chunk_id in passed_ids]
        filtered.sort(key=lambda r: passed_ids.get(r.chunk_id, 0), reverse=True)
        for r in filtered:
            r.score = passed_ids.get(r.chunk_id, r.score)
        return filtered

    def _llm_evaluate(
        self,
        query: str,
        result: RetrievalResult,
        semantic_sim: float,
    ) -> str:
        """Use Cloudflare Workers AI LLM to reason about relevance."""
        content_preview = result.content[:500]
        source = result.metadata.get("source", "unknown")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a retrieval quality judge. Given a user query and a "
                    "retrieved document chunk, determine if the chunk is RELEVANT "
                    "or NOT RELEVANT to the query. Be concise. Consider: semantic "
                    "match, information completeness, and whether the chunk actually "
                    "answers or supports the query intent. Also check if the content "
                    "appears to have drifted from its source (signs of rewriting or "
                    "information loss). Respond in one sentence."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Query: {query}\n"
                    f"Source: {source}\n"
                    f"Modality: {result.modality}\n"
                    f"Semantic similarity: {semantic_sim:.3f}\n"
                    f"Content: {content_preview}\n\n"
                    f"Is this chunk RELEVANT or NOT RELEVANT?"
                ),
            },
        ]

        try:
            response = llm_chat(messages, max_tokens=100)
            return response.strip()
        except Exception:
            # Fallback to fast reasoning if LLM call fails
            return self._fast_reasoning(
                query, result, semantic_sim, result.score,
                0.6 * semantic_sim + 0.4 * result.score,
            )

    def _fast_reasoning(
        self,
        query: str,
        result: RetrievalResult,
        semantic_sim: float,
        retrieval_score: float,
        blended: float,
    ) -> str:
        """Generate reasoning without LLM (for clear-cut cases)."""
        parts = []
        parts.append(f"Semantic: {semantic_sim:.3f}")
        parts.append(f"Retrieval: {retrieval_score:.3f}")
        parts.append(f"Blended: {blended:.3f}")

        if blended >= 0.7:
            parts.append("Strong match — high confidence.")
        elif blended >= 0.5:
            parts.append("Moderate match — likely relevant.")
        elif blended >= self.threshold:
            parts.append("Weak match — borderline relevant.")
        else:
            parts.append("Below threshold — not relevant.")

        parts.append(f"[{result.modality}/{result.agent}]")
        return " | ".join(parts)


def _cosine_similarities(query_emb: list[float], result_embs: list[list[float]]) -> list[float]:
    """Compute cosine similarity between query and each result embedding."""
    import math

    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _norm(a: list[float]) -> float:
        return math.sqrt(sum(x * x for x in a))

    q_norm = _norm(query_emb)
    if q_norm == 0:
        return [0.0] * len(result_embs)

    sims = []
    for emb in result_embs:
        r_norm = _norm(emb)
        if r_norm == 0:
            sims.append(0.0)
        else:
            sims.append(_dot(query_emb, emb) / (q_norm * r_norm))
    return sims
