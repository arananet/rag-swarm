"""Pydantic models for the RAG Swarm API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Modality(str, Enum):
    TEXT = "text"
    PDF = "pdf"
    IMAGE = "image"
    CODE = "code"
    TABLE = "table"


class DocumentChunk(BaseModel):
    id: str
    content: str
    modality: Modality
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class IngestRequest(BaseModel):
    collection: str = "default"


class IngestResponse(BaseModel):
    collection: str
    documents_processed: int
    chunks_created: int
    modalities: list[str]


class QueryRequest(BaseModel):
    query: str
    collection: str = "default"
    top_k: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)


class RetrievalResult(BaseModel):
    chunk_id: str
    content: str
    modality: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    agent: str


class OracleVerdict(BaseModel):
    chunk_id: str
    relevance_score: float
    reasoning: str
    passed: bool


class SwarmQueryResponse(BaseModel):
    query: str
    results: list[RetrievalResult]
    oracle_verdicts: list[OracleVerdict]
    total_candidates: int
    filtered_count: int
    agents_used: list[str]


class TraditionalQueryResponse(BaseModel):
    query: str
    results: list[RetrievalResult]
    total_results: int


class EvaluationMetrics(BaseModel):
    precision: float
    recall: float
    ndcg: float
    mrr: float
    avg_relevance: float


class CompareResponse(BaseModel):
    query: str
    swarm: SwarmQueryResponse
    traditional: TraditionalQueryResponse
    swarm_metrics: EvaluationMetrics
    traditional_metrics: EvaluationMetrics
    improvement: dict[str, float]


class CollectionInfo(BaseModel):
    name: str
    count: int
    modalities: dict[str, int]
