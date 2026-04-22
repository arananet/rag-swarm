"""MCP Server — Expose RAG Swarm as a Model Context Protocol server.

Implements MCP spec 2025-11-25 using the official Python SDK (FastMCP).
Supports stdio and Streamable HTTP transports.

Usage:
  # stdio (for Claude Desktop / Claude Code)
  python -m app.mcp_server

  # Streamable HTTP (for MCP Inspector / browser clients)
  python -m app.mcp_server --transport streamable-http --port 8001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

from app.agents.dispatcher import dispatch_swarm, merge_results
from app.agents.oracle import OracleAgent
from app.agents.reranker import deduplicate_results, rerank_results
from app.agents.traditional import traditional_query
from app.evaluation.metrics import compute_improvement, compute_metrics
from app.ingestion.pipeline import ingest_directory
from app.vectorstore import collection_stats, list_collections

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "RAG Swarm",
    instructions=(
        "A multimodal Swarm Agent RAG system with multi-agent vector retrieval, "
        "oracle evaluation, and provenance tracking. Powered by Cloudflare Workers AI. "
        "Use the tools to query a knowledge base, compare retrieval strategies, "
        "ingest sample data, or inspect collections."
    ),
    stateless_http=True,
    json_response=True,
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def rag_query(
    query: str,
    collection: str = "default",
    top_k: int = 10,
    threshold: float = 0.3,
) -> dict[str, Any]:
    """Search the knowledge base using swarm multi-agent retrieval with oracle evaluation.

    Dispatches query to specialized agents (Text, Code, Image, Table, PDF),
    deduplicates, re-ranks with a cross-encoder, and filters through an
    LLM-powered oracle that provides relevance reasoning.

    Args:
        query: Natural-language search query.
        collection: ChromaDB collection to search (default: "default").
        top_k: Maximum number of results to return (1-100).
        threshold: Oracle relevance threshold (0.0-1.0).
    """
    agent_results = await dispatch_swarm(query=query, collection=collection, top_k=top_k)
    all_results = merge_results(agent_results)
    total_candidates = len(all_results)

    deduped = deduplicate_results(all_results)
    reranked = rerank_results(query, deduped, top_k=top_k * 2)

    oracle = OracleAgent(threshold=threshold)
    verdicts = oracle.evaluate(query, reranked)
    filtered = oracle.filter_results(reranked, verdicts)

    agents_used = list({ar.agent_name for ar in agent_results if ar.results})

    return {
        "query": query,
        "total_candidates": total_candidates,
        "filtered_count": len(filtered),
        "agents_used": agents_used,
        "results": [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "modality": r.modality,
                "score": round(r.score, 4),
                "agent": r.agent,
                "metadata": r.metadata,
            }
            for r in filtered
        ],
        "oracle_verdicts": [
            {
                "chunk_id": v.chunk_id,
                "relevance_score": round(v.relevance_score, 4),
                "reasoning": v.reasoning,
                "passed": v.passed,
            }
            for v in verdicts
        ],
    }


@mcp.tool()
def rag_query_traditional(
    query: str,
    collection: str = "default",
    top_k: int = 10,
) -> dict[str, Any]:
    """Search the knowledge base using traditional single-retriever RAG (baseline).

    Uses a single embedding lookup without specialized agents or oracle filtering.
    Useful as a baseline comparison against the swarm approach.

    Args:
        query: Natural-language search query.
        collection: ChromaDB collection to search.
        top_k: Maximum number of results to return.
    """
    results = traditional_query(query=query, collection=collection, top_k=top_k)
    return {
        "query": query,
        "total_results": len(results),
        "results": [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "modality": r.modality,
                "score": round(r.score, 4),
                "agent": r.agent,
                "metadata": r.metadata,
            }
            for r in results
        ],
    }


@mcp.tool()
async def rag_compare(
    query: str,
    collection: str = "default",
    top_k: int = 10,
    threshold: float = 0.3,
) -> dict[str, Any]:
    """Compare swarm multi-agent RAG vs traditional single-retriever RAG side by side.

    Returns results from both approaches with evaluation metrics (precision,
    recall, NDCG, MRR) and percentage improvement.

    Args:
        query: Natural-language search query.
        collection: ChromaDB collection to search.
        top_k: Maximum number of results to return per approach.
        threshold: Oracle relevance threshold for the swarm approach.
    """
    # Swarm path
    agent_results = await dispatch_swarm(query=query, collection=collection, top_k=top_k)
    all_swarm = merge_results(agent_results)
    deduped = deduplicate_results(all_swarm)
    reranked = rerank_results(query, deduped, top_k=top_k * 2)
    oracle = OracleAgent(threshold=threshold)
    verdicts = oracle.evaluate(query, reranked)
    filtered = oracle.filter_results(reranked, verdicts)
    agents_used = list({ar.agent_name for ar in agent_results if ar.results})

    # Traditional path
    trad_results = traditional_query(query=query, collection=collection, top_k=top_k)

    # Metrics
    swarm_metrics = compute_metrics(filtered, verdicts, threshold=threshold)
    trad_metrics = compute_metrics(trad_results, threshold=threshold)
    improvement = compute_improvement(swarm_metrics, trad_metrics)

    def _serialize_metrics(m):
        return {
            "precision": round(m.precision, 4),
            "recall": round(m.recall, 4),
            "ndcg": round(m.ndcg, 4),
            "mrr": round(m.mrr, 4),
            "avg_relevance": round(m.avg_relevance, 4),
        }

    return {
        "query": query,
        "swarm": {
            "filtered_count": len(filtered),
            "total_candidates": len(all_swarm),
            "agents_used": agents_used,
            "results_count": len(filtered),
        },
        "traditional": {
            "total_results": len(trad_results),
        },
        "swarm_metrics": _serialize_metrics(swarm_metrics),
        "traditional_metrics": _serialize_metrics(trad_metrics),
        "improvement": improvement,
    }


@mcp.tool()
def ingest_sample_data(collection: str = "default") -> dict[str, Any]:
    """Ingest the bundled sample_data directory into the vector store for demo purposes.

    Processes markdown, Python, and other supported files through the
    multimodal ingestion pipeline (chunking, VLM captioning, provenance tracking).

    Args:
        collection: Target ChromaDB collection name.
    """
    sample_dir = Path(__file__).parent.parent / "sample_data"
    if not sample_dir.exists():
        return {"error": "sample_data directory not found"}

    files_processed, chunks_created, modalities = ingest_directory(sample_dir, collection)
    return {
        "collection": collection,
        "documents_processed": files_processed,
        "chunks_created": chunks_created,
        "modalities": sorted(modalities),
    }


@mcp.tool()
def list_all_collections() -> list[dict[str, Any]]:
    """List all ChromaDB collections with document counts and modality breakdowns.

    Returns a list of collections, each with name, document count, and a
    mapping of modality → count.
    """
    names = list_collections()
    return [collection_stats(name) for name in names]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("rag://collections")
def get_collections_resource() -> str:
    """Overview of all available ChromaDB collections and their statistics."""
    names = list_collections()
    data = [collection_stats(name) for name in names]
    return json.dumps(data, indent=2)


@mcp.resource("rag://collection/{name}")
def get_collection_detail(name: str) -> str:
    """Detailed statistics for a specific ChromaDB collection including modality counts."""
    data = collection_stats(name)
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt(title="RAG Search")
def rag_search_prompt(query: str, collection: str = "default") -> str:
    """Search the RAG knowledge base with the swarm multi-agent approach."""
    return (
        f"Use the rag_query tool to search for: {query}\n"
        f"Collection: {collection}\n\n"
        "Summarize the top results, noting which agents found them and "
        "the oracle's relevance reasoning for each."
    )


@mcp.prompt(title="RAG Compare")
def rag_compare_prompt(query: str) -> list[base.Message]:
    """Compare swarm RAG vs traditional RAG approaches side-by-side."""
    return [
        base.UserMessage(
            f"Use the rag_compare tool with the query: {query}\n\n"
            "Then provide a clear comparison table showing:\n"
            "1. Metrics (precision, recall, NDCG, MRR) for each approach\n"
            "2. Percentage improvement\n"
            "3. Which agents contributed to the swarm results\n"
            "4. Your analysis of why one approach performed better"
        ),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="RAG Swarm MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for streamable-http transport (default: 8001)",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
