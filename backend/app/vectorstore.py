"""ChromaDB vector store wrapper — manages collections and operations."""

from __future__ import annotations

import chromadb
from chromadb.config import Settings

_client: chromadb.ClientAPI | None = None

CHROMA_PERSIST_DIR = "./chroma_data"


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_or_create_collection(name: str) -> chromadb.Collection:
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    coll = get_or_create_collection(collection_name)
    # ChromaDB add is idempotent on IDs
    coll.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def query_collection(
    collection_name: str,
    query_embedding: list[float],
    n_results: int = 10,
    where: dict | None = None,
) -> dict:
    coll = get_or_create_collection(collection_name)
    if coll.count() == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(n_results, coll.count()),
    }
    if where:
        kwargs["where"] = where
    return coll.query(**kwargs)


def collection_stats(collection_name: str) -> dict:
    coll = get_or_create_collection(collection_name)
    count = coll.count()
    modality_counts: dict[str, int] = {}
    if count > 0:
        # Sample all metadata to count modalities
        all_data = coll.get(limit=count, include=["metadatas"])
        for meta in all_data["metadatas"]:
            mod = meta.get("modality", "unknown")
            modality_counts[mod] = modality_counts.get(mod, 0) + 1
    return {"name": collection_name, "count": count, "modalities": modality_counts}


def list_collections() -> list[str]:
    client = get_client()
    return [c.name for c in client.list_collections()]
