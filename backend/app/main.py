"""FastAPI application — Swarm Agent RAG API."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agents.dispatcher import dispatch_swarm, merge_results
from app.agents.oracle import OracleAgent
from app.agents.reranker import deduplicate_results, rerank_results
from app.agents.traditional import traditional_query
from app.cache import query_cache
from app.embeddings import embed_text
from app.evaluation.metrics import compute_improvement, compute_metrics
from app.ingestion.pipeline import ingest_directory, ingest_file
from app.models.schemas import (
    CacheStats,
    CollectionInfo,
    CompareResponse,
    EvaluationMetrics,
    IngestResponse,
    QueryRequest,
    SwarmQueryResponse,
    TraditionalQueryResponse,
)
from app.vectorstore import collection_stats, list_collections

app = FastAPI(
    title="RAG Swarm API",
    description="Multimodal Swarm Agent RAG with Oracle Evaluation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://localhost:3000", "http://localhost:8000", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: list[UploadFile] = File(...),
    collection: str = "default",
):
    """Ingest uploaded files into the vector store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        for upload in files:
            # Sanitize filename to prevent path traversal
            safe_name = Path(upload.filename).name
            dest = tmppath / safe_name
            with open(dest, "wb") as f:
                content = await upload.read()
                f.write(content)

        files_processed, chunks_created, modalities = ingest_directory(
            tmppath, collection
        )

    return IngestResponse(
        collection=collection,
        documents_processed=files_processed,
        chunks_created=chunks_created,
        modalities=sorted(modalities),
    )


@app.post("/query", response_model=SwarmQueryResponse)
async def query_swarm(req: QueryRequest):
    """Swarm agent retrieval with oracle evaluation."""
    # --- Cache lookup ---
    query_embedding = embed_text(req.query)
    cached, similarity = query_cache.lookup(req.query, query_embedding)
    if cached is not None:
        return SwarmQueryResponse(**{**cached, "cache_hit": True, "cache_similarity": similarity})

    # Dispatch to all swarm agents
    agent_results = await dispatch_swarm(
        query=req.query,
        collection=req.collection,
        top_k=req.top_k,
    )

    # Merge results from all agents
    all_results = merge_results(agent_results)
    total_candidates = len(all_results)

    # Multi-stage retrieval: deduplicate → rerank → oracle
    deduped = deduplicate_results(all_results)
    reranked = rerank_results(req.query, deduped, top_k=req.top_k * 2)

    # Oracle evaluation (LLM-powered)
    oracle = OracleAgent(threshold=req.threshold)
    verdicts = oracle.evaluate(req.query, reranked)
    filtered = oracle.filter_results(reranked, verdicts)

    agents_used = list({ar.agent_name for ar in agent_results if ar.results})

    response = SwarmQueryResponse(
        query=req.query,
        results=filtered,
        oracle_verdicts=verdicts,
        total_candidates=total_candidates,
        filtered_count=len(filtered),
        agents_used=agents_used,
    )

    # --- Cache store ---
    query_cache.store(req.query, query_embedding, response.model_dump())

    return response


@app.post("/query-traditional", response_model=TraditionalQueryResponse)
async def query_traditional(req: QueryRequest):
    """Traditional single-retriever RAG baseline."""
    # --- Cache lookup ---
    query_embedding = embed_text(req.query)
    cache_key = f"trad:{req.query}"
    cached, similarity = query_cache.lookup(cache_key, query_embedding)
    if cached is not None:
        return TraditionalQueryResponse(**{**cached, "cache_hit": True, "cache_similarity": similarity})

    results = traditional_query(
        query=req.query,
        collection=req.collection,
        top_k=req.top_k,
    )
    response = TraditionalQueryResponse(
        query=req.query,
        results=results,
        total_results=len(results),
    )

    # --- Cache store ---
    query_cache.store(cache_key, query_embedding, response.model_dump())

    return response


@app.post("/compare", response_model=CompareResponse)
async def compare(req: QueryRequest):
    """Side-by-side comparison of swarm vs traditional RAG with metrics."""
    # --- Cache lookup ---
    query_embedding = embed_text(req.query)
    cache_key = f"compare:{req.query}"
    cached, similarity = query_cache.lookup(cache_key, query_embedding)
    if cached is not None:
        return CompareResponse(**{**cached, "cache_hit": True, "cache_similarity": similarity})

    # Run swarm query
    agent_results = await dispatch_swarm(
        query=req.query, collection=req.collection, top_k=req.top_k
    )
    all_swarm = merge_results(agent_results)
    deduped = deduplicate_results(all_swarm)
    reranked = rerank_results(req.query, deduped, top_k=req.top_k * 2)
    oracle = OracleAgent(threshold=req.threshold)
    verdicts = oracle.evaluate(req.query, reranked)
    filtered = oracle.filter_results(reranked, verdicts)
    agents_used = list({ar.agent_name for ar in agent_results if ar.results})

    swarm_response = SwarmQueryResponse(
        query=req.query,
        results=filtered,
        oracle_verdicts=verdicts,
        total_candidates=len(all_swarm),
        filtered_count=len(filtered),
        agents_used=agents_used,
    )

    # Run traditional query
    trad_results = traditional_query(
        query=req.query, collection=req.collection, top_k=req.top_k
    )
    trad_response = TraditionalQueryResponse(
        query=req.query, results=trad_results, total_results=len(trad_results)
    )

    # Compute metrics
    swarm_metrics = compute_metrics(filtered, verdicts, threshold=req.threshold)

    # For traditional, create pseudo-verdicts based on score threshold
    trad_metrics = compute_metrics(trad_results, threshold=req.threshold)

    improvement = compute_improvement(swarm_metrics, trad_metrics)

    response = CompareResponse(
        query=req.query,
        swarm=swarm_response,
        traditional=trad_response,
        swarm_metrics=swarm_metrics,
        traditional_metrics=trad_metrics,
        improvement=improvement,
    )

    # --- Cache store ---
    query_cache.store(cache_key, query_embedding, response.model_dump())

    return response


@app.get("/cache/stats", response_model=CacheStats)
async def cache_stats():
    """Return cache statistics."""
    return CacheStats(**query_cache.stats())


@app.delete("/cache/clear")
async def cache_clear():
    """Clear all cached entries."""
    removed = query_cache.clear()
    return {"cleared": removed}


@app.get("/collections", response_model=list[CollectionInfo])
async def get_collections():
    """List all collections with stats."""
    names = list_collections()
    return [CollectionInfo(**collection_stats(name)) for name in names]


@app.post("/ingest-sample")
async def ingest_sample(collection: str = "default"):
    """Ingest the sample_data directory for demo purposes."""
    sample_dir = Path(__file__).parent.parent.parent / "sample_data"
    if not sample_dir.exists():
        return {"error": "sample_data directory not found"}

    files_processed, chunks_created, modalities = ingest_directory(
        sample_dir, collection
    )
    return IngestResponse(
        collection=collection,
        documents_processed=files_processed,
        chunks_created=chunks_created,
        modalities=sorted(modalities),
    )
