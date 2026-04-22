"""Semantic query cache — avoids redundant Cloudflare API calls.

Caches query embeddings + full responses.  On each new query the embedding
is compared (cosine similarity) against cached vectors.  If similarity ≥
threshold the cached response is returned directly, skipping swarm dispatch,
reranking, oracle, and all external API calls.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration via env vars (sensible defaults)
# ---------------------------------------------------------------------------
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "256"))


@dataclass
class _CacheEntry:
    query: str
    embedding: np.ndarray
    response: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    last_hit: float = field(default_factory=time.time)
    hit_count: int = 0


class SemanticQueryCache:
    """Thread-safe in-memory semantic cache with LRU eviction and TTL."""

    def __init__(
        self,
        similarity_threshold: float = CACHE_SIMILARITY_THRESHOLD,
        ttl: int = CACHE_TTL_SECONDS,
        max_size: int = CACHE_MAX_SIZE,
    ):
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self.max_size = max_size

        # Stats
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(
        self, query: str, query_embedding: list[float]
    ) -> tuple[dict[str, Any] | None, float]:
        """Check cache for a semantically similar query.

        Returns ``(cached_response, similarity)`` or ``(None, 0.0)``.
        """
        if not CACHE_ENABLED:
            self._misses += 1
            return None, 0.0

        qvec = np.asarray(query_embedding, dtype=np.float32)
        now = time.time()

        with self._lock:
            self._evict_expired(now)

            best_sim = 0.0
            best_key: str | None = None

            for key, entry in self._entries.items():
                sim = self._cosine_similarity(qvec, entry.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_key = key

            if best_key is not None and best_sim >= self.similarity_threshold:
                entry = self._entries[best_key]
                entry.last_hit = now
                entry.hit_count += 1
                self._hits += 1
                return entry.response, float(best_sim)

        self._misses += 1
        return None, float(best_sim)

    def store(
        self,
        query: str,
        query_embedding: list[float],
        response: dict[str, Any],
    ) -> None:
        """Store a query + response in the cache."""
        if not CACHE_ENABLED:
            return

        qvec = np.asarray(query_embedding, dtype=np.float32)
        key = self._query_key(query)

        with self._lock:
            if len(self._entries) >= self.max_size:
                self._evict_lru()
            self._entries[key] = _CacheEntry(
                query=query,
                embedding=qvec,
                response=response,
            )

    def clear(self) -> int:
        """Remove all entries. Returns count of entries removed."""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._hits = 0
            self._misses = 0
            return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "enabled": CACHE_ENABLED,
                "entries": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "similarity_threshold": self.similarity_threshold,
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        dot = float(np.dot(a, b))
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        if norm == 0:
            return 0.0
        return dot / norm

    @staticmethod
    def _query_key(query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]

    def _evict_expired(self, now: float) -> None:
        """Remove entries older than TTL (caller holds the lock)."""
        expired = [
            k for k, e in self._entries.items() if now - e.created_at > self.ttl
        ]
        for k in expired:
            del self._entries[k]

    def _evict_lru(self) -> None:
        """Remove the least-recently-used entry (caller holds the lock)."""
        if not self._entries:
            return
        lru_key = min(self._entries, key=lambda k: self._entries[k].last_hit)
        del self._entries[lru_key]


# ---------------------------------------------------------------------------
# Module-level singleton — shared across the app
# ---------------------------------------------------------------------------
query_cache = SemanticQueryCache()
