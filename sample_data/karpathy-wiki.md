# Karpathy's LLM Wiki Architecture

## Three-Layer Design

Andrej Karpathy's LLM Wiki pattern uses a three-layer architecture for building AI-maintained knowledge bases:

### Layer 1: Raw Sources (raw/)
Immutable source documents — articles, papers, code repos. The LLM reads these but never modifies them. They serve as the verification baseline.

### Layer 2: The Wiki (wiki/)
LLM-generated markdown pages organized by type:
- concepts/ — Concept pages
- entities/ — Entity pages  
- sources/ — Source summaries
- comparisons/ — Comparison pages

Two structural files: index.md (content catalog) and log.md (append-only operation log).

### Layer 3: The Schema (CLAUDE.md)
Configuration file that defines structure, naming conventions, page templates, and operational workflows.

## Three Operations

1. **Ingest** — Process new sources, create summaries, update cross-references, update index
2. **Query** — Search via index, read relevant pages, synthesize answers with citations
3. **Lint** — Check for contradictions, orphans, missing concepts, stale claims

## LLM Wiki vs RAG

| Aspect | RAG | LLM Wiki |
|---|---|---|
| State | Stateless per query | Stateful, knowledge compounds |
| Infrastructure | Vector DB + embedding pipeline | Folder of .md files |
| Cross-references | Ad-hoc per query | Pre-built by LLM |
| Token cost/query | High (retrieve + re-rank + generate) | Low (index + targeted pages) |
| Scale sweet spot | Enterprise (millions of docs) | Personal/team (<100K tokens) |

## Connection to Swarm RAG

The Karpathy LLM Wiki and Swarm RAG address the same fundamental problem from different angles:
- LLM Wiki: Pre-compiled knowledge with explicit cross-references
- Swarm RAG: Runtime retrieval with multi-agent coverage

A hybrid approach uses Karpathy's three-layer architecture for knowledge organization while deploying swarm agents for retrieval across the structured wiki pages. The oracle agent then serves as the "lint" layer — evaluating result quality in real-time.
