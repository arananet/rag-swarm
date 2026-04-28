"""FastAPI application — Swarm Agent RAG API."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
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
    WikiLintResult,
    WikiPage,
)
from app.vectorstore import collection_stats, list_collections
from app.wiki.manager import wiki_manager

app = FastAPI(
    title="RAG Swarm API",
    description="Multimodal Swarm Agent RAG with Oracle Evaluation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://localhost:3000", "http://localhost:8000", "http://localhost:5174", "http://localhost:5173"],
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
        wiki_pages_written=wiki_manager.list_pages(collection),
    )


@app.post("/query", response_model=SwarmQueryResponse)
async def query_swarm(req: QueryRequest):
    """Swarm agent retrieval with oracle evaluation."""
    # --- Cache lookup ---
    query_embedding = embed_text(req.query)
    cached, similarity = query_cache.lookup(req.query, query_embedding)
    if cached is not None:
        # Guard against stale cache entries missing required fields (e.g. after schema changes)
        if all(k in cached for k in ("results", "oracle_verdicts", "total_candidates", "filtered_count", "agents_used")):
            cached.setdefault("wiki_pages", [])
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

    # --- Wiki layer: pre-synthesised pages (Karpathy layer 2) ---
    wiki_pages = wiki_manager.get_relevant_pages(
        query=req.query, collection=req.collection, top_k=3
    )

    response = SwarmQueryResponse(
        query=req.query,
        results=filtered,
        oracle_verdicts=verdicts,
        total_candidates=total_candidates,
        filtered_count=len(filtered),
        agents_used=agents_used,
        wiki_pages=wiki_pages,
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
        if all(k in cached for k in ("results", "total_results")):
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
        if all(k in cached for k in ("swarm", "traditional", "swarm_metrics", "traditional_metrics")):
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
        wiki_pages_written=wiki_manager.list_pages(collection),
    )


# ---------------------------------------------------------------------------
# Wiki endpoints (Karpathy layer 2)
# ---------------------------------------------------------------------------

@app.get("/wiki/{collection}/pages", response_model=list[str])
async def wiki_list_pages(collection: str = "default"):
    """List all wiki page slugs in a collection."""
    return wiki_manager.list_pages(collection)


@app.get("/wiki/{collection}/pages/{slug}", response_model=WikiPage)
async def wiki_read_page(slug: str, collection: str = "default"):
    """Return the content of a single wiki page."""
    content = wiki_manager.read_page(slug, collection)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Wiki page '{slug}' not found in collection '{collection}'")
    title = slug
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return WikiPage(slug=slug, title=title, content=content, collection=collection)


@app.get("/wiki/{collection}/index")
async def wiki_index(collection: str = "default"):
    """Return the wiki index.md (page catalog)."""
    return {"collection": collection, "index": wiki_manager.read_index(collection)}


@app.get("/wiki/{collection}/log")
async def wiki_log(collection: str = "default"):
    """Return the wiki log.md (chronological ingest/query history)."""
    return {"collection": collection, "log": wiki_manager.read_log(collection)}


@app.post("/wiki/{collection}/lint", response_model=WikiLintResult)
async def wiki_lint(collection: str = "default"):
    """Ask the LLM to health-check the wiki (contradictions, orphans, stale claims)."""
    report = wiki_manager.lint(collection)
    return WikiLintResult(report=report)
