"""Traditional single-retriever RAG — baseline for comparison against swarm."""

from __future__ import annotations

from app.embeddings import embed_text
from app.models.schemas import RetrievalResult
from app.vectorstore import query_collection


def traditional_query(
    query: str,
    collection: str = "default",
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Single-retriever RAG: embed query, search entire collection, return top-k.
    
    No modality specialization, no oracle filtering — just raw cosine similarity.
    """
    query_emb = embed_text(query)

    raw = query_collection(
        collection_name=collection,
        query_embedding=query_emb,
        n_results=top_k,
        where=None,  # No modality filter — search everything
    )

    results: list[RetrievalResult] = []
    if raw["ids"] and raw["ids"][0]:
        for i, cid in enumerate(raw["ids"][0]):
            distance = raw["distances"][0][i] if raw["distances"] and raw["distances"][0] else 1.0
            score = max(0.0, 1.0 - distance)
            results.append(
                RetrievalResult(
                    chunk_id=cid,
                    content=raw["documents"][0][i] if raw["documents"] else "",
                    modality=raw["metadatas"][0][i].get("modality", "unknown"),
                    score=score,
                    metadata=raw["metadatas"][0][i] if raw["metadatas"] else {},
                    agent="TraditionalRetriever",
                )
            )

    return sorted(results, key=lambda r: r.score, reverse=True)
