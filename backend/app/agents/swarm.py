"""Base swarm agent and modality-specialized agents for vector retrieval."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.embeddings import embed_text
from app.models.schemas import Modality, RetrievalResult
from app.vectorstore import query_collection


@dataclass
class AgentResult:
    agent_name: str
    results: list[RetrievalResult]
    modality: Modality
    search_time_ms: float = 0.0


class SwarmAgent(ABC):
    """Base class for all swarm retrieval agents."""

    def __init__(self, name: str, modality: Modality, top_k: int = 5):
        self.name = name
        self.modality = modality
        self.top_k = top_k

    @abstractmethod
    def build_query(self, user_query: str) -> str:
        """Transform user query for this agent's specialization."""
        ...

    def _modality_filter(self) -> dict | None:
        """ChromaDB where filter for this agent's modality."""
        return {"modality": self.modality.value}

    async def search(self, user_query: str, collection: str) -> AgentResult:
        """Execute vector search for this agent's modality."""
        import time

        start = time.perf_counter()
        enriched_query = self.build_query(user_query)
        query_emb = embed_text(enriched_query)

        raw = query_collection(
            collection_name=collection,
            query_embedding=query_emb,
            n_results=self.top_k,
            where=self._modality_filter(),
        )

        results: list[RetrievalResult] = []
        if raw["ids"] and raw["ids"][0]:
            for i, cid in enumerate(raw["ids"][0]):
                distance = raw["distances"][0][i] if raw["distances"] and raw["distances"][0] else 1.0
                score = 1.0 - distance  # cosine distance → similarity
                results.append(
                    RetrievalResult(
                        chunk_id=cid,
                        content=raw["documents"][0][i] if raw["documents"] else "",
                        modality=raw["metadatas"][0][i].get("modality", self.modality.value),
                        score=max(0.0, score),
                        metadata=raw["metadatas"][0][i] if raw["metadatas"] else {},
                        agent=self.name,
                    )
                )

        elapsed = (time.perf_counter() - start) * 1000
        return AgentResult(
            agent_name=self.name,
            results=sorted(results, key=lambda r: r.score, reverse=True),
            modality=self.modality,
            search_time_ms=elapsed,
        )


class TextAgent(SwarmAgent):
    """Retrieves text chunks — articles, documentation, plain text."""

    def __init__(self, top_k: int = 5):
        super().__init__("TextAgent", Modality.TEXT, top_k)

    def build_query(self, user_query: str) -> str:
        return user_query


class CodeAgent(SwarmAgent):
    """Retrieves code chunks — functions, classes, code snippets."""

    def __init__(self, top_k: int = 5):
        super().__init__("CodeAgent", Modality.CODE, top_k)

    def build_query(self, user_query: str) -> str:
        return f"code implementation: {user_query}"


class ImageAgent(SwarmAgent):
    """Retrieves image descriptions and visual content."""

    def __init__(self, top_k: int = 5):
        super().__init__("ImageAgent", Modality.IMAGE, top_k)

    def build_query(self, user_query: str) -> str:
        return f"image visual: {user_query}"


class TableAgent(SwarmAgent):
    """Retrieves structured data — tables, CSVs, data grids."""

    def __init__(self, top_k: int = 5):
        super().__init__("TableAgent", Modality.TABLE, top_k)

    def build_query(self, user_query: str) -> str:
        return f"data table: {user_query}"


class PDFAgent(SwarmAgent):
    """Retrieves PDF document chunks."""

    def __init__(self, top_k: int = 5):
        super().__init__("PDFAgent", Modality.PDF, top_k)

    def build_query(self, user_query: str) -> str:
        return user_query
