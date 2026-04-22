"""Swarm dispatcher — fans out queries to all agents in parallel and collects results."""

from __future__ import annotations

import asyncio

from app.agents.swarm import (
    AgentResult,
    CodeAgent,
    ImageAgent,
    PDFAgent,
    SwarmAgent,
    TableAgent,
    TextAgent,
)
from app.models.schemas import RetrievalResult


def create_default_swarm(top_k: int = 5) -> list[SwarmAgent]:
    """Create the default set of swarm agents."""
    return [
        TextAgent(top_k=top_k),
        CodeAgent(top_k=top_k),
        ImageAgent(top_k=top_k),
        TableAgent(top_k=top_k),
        PDFAgent(top_k=top_k),
    ]


async def dispatch_swarm(
    query: str,
    collection: str = "default",
    top_k: int = 5,
    agents: list[SwarmAgent] | None = None,
) -> list[AgentResult]:
    """Dispatch query to all swarm agents in parallel."""
    if agents is None:
        agents = create_default_swarm(top_k=top_k)

    tasks = [agent.search(query, collection) for agent in agents]
    results = await asyncio.gather(*tasks)
    return list(results)


def merge_results(agent_results: list[AgentResult]) -> list[RetrievalResult]:
    """Merge and deduplicate results from all agents, sorted by score."""
    seen: set[str] = set()
    merged: list[RetrievalResult] = []
    for ar in agent_results:
        for result in ar.results:
            if result.chunk_id not in seen:
                seen.add(result.chunk_id)
                merged.append(result)
    return sorted(merged, key=lambda r: r.score, reverse=True)
