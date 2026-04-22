"""Provenance tracking and drift detection.

Innovations addressing Karpathy criticism:
- Context degradation: tracks embedding versions so stale chunks can be refreshed
  when the model changes or content is updated.
- Model collapse: computes drift between current embeddings and stored originals
  to detect information loss or semantic drift over re-indexing cycles.
- Multi-agent governance: provides transparent metadata for every chunk, enabling
  audit trails and root-cause analysis when retrieval quality degrades.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field


@dataclass
class ProvenanceRecord:
    """Tracks the origin and lifecycle of each indexed chunk."""

    chunk_id: str
    source_file: str
    source_hash: str              # SHA-256 of original file at ingest time
    modality: str
    ingest_timestamp: float
    embedding_model: str          # e.g. "@cf/baai/bge-base-en-v1.5"
    embedding_version: str        # hash of model name + date for cache busting
    chunk_index: int              # position within source file
    total_chunks: int             # how many chunks the source produced
    content_hash: str             # SHA-256 of the chunk content itself
    parent_chunk_id: str | None = None  # for hierarchical chunks


@dataclass
class DriftReport:
    """Result of drift detection between two embedding versions."""

    chunk_id: str
    drift_score: float            # cosine distance between old and new embedding
    is_drifted: bool              # above threshold?
    old_model: str
    new_model: str


class ProvenanceTracker:
    """Manages provenance metadata for ingested chunks."""

    def __init__(self, embedding_model: str = "@cf/baai/bge-base-en-v1.5"):
        self.embedding_model = embedding_model
        self.embedding_version = hashlib.sha256(
            f"{embedding_model}:{int(time.time() // 86400)}".encode()
        ).hexdigest()[:8]

    def create_record(
        self,
        chunk_id: str,
        source_file: str,
        source_content: bytes,
        chunk_content: str,
        modality: str,
        chunk_index: int,
        total_chunks: int,
        parent_chunk_id: str | None = None,
    ) -> ProvenanceRecord:
        """Create a provenance record for a newly ingested chunk."""
        return ProvenanceRecord(
            chunk_id=chunk_id,
            source_file=source_file,
            source_hash=hashlib.sha256(source_content).hexdigest(),
            modality=modality,
            ingest_timestamp=time.time(),
            embedding_model=self.embedding_model,
            embedding_version=self.embedding_version,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            content_hash=hashlib.sha256(chunk_content.encode()).hexdigest(),
            parent_chunk_id=parent_chunk_id,
        )

    def to_metadata(self, record: ProvenanceRecord) -> dict:
        """Convert a provenance record to ChromaDB metadata format."""
        meta = {
            "source": record.source_file,
            "source_hash": record.source_hash,
            "modality": record.modality,
            "ingest_ts": record.ingest_timestamp,
            "embed_model": record.embedding_model,
            "embed_version": record.embedding_version,
            "chunk_idx": record.chunk_index,
            "total_chunks": record.total_chunks,
            "content_hash": record.content_hash,
        }
        if record.parent_chunk_id:
            meta["parent_chunk_id"] = record.parent_chunk_id
        return meta

    @staticmethod
    def detect_drift(
        old_embedding: list[float],
        new_embedding: list[float],
        threshold: float = 0.05,
        old_model: str = "",
        new_model: str = "",
        chunk_id: str = "",
    ) -> DriftReport:
        """Detect embedding drift between two versions of the same chunk.

        A cosine distance above `threshold` indicates the chunk's semantic
        representation has shifted — potentially due to model updates,
        content changes, or information degradation.
        """
        cos_sim = _cosine_sim(old_embedding, new_embedding)
        drift_score = 1.0 - cos_sim  # cosine distance

        return DriftReport(
            chunk_id=chunk_id,
            drift_score=round(drift_score, 6),
            is_drifted=drift_score > threshold,
            old_model=old_model,
            new_model=new_model,
        )

    @staticmethod
    def check_source_freshness(
        stored_hash: str,
        current_content: bytes,
    ) -> bool:
        """Check if the source file has changed since ingestion."""
        current_hash = hashlib.sha256(current_content).hexdigest()
        return stored_hash == current_hash


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
