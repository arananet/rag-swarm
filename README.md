# rag-swarm

[![Spec Check](https://github.com/arananet/rag-swarm/actions/workflows/spec-check.yml/badge.svg)](https://github.com/arananet/rag-swarm/actions/workflows/spec-check.yml)
[![CodeQL](https://github.com/arananet/rag-swarm/actions/workflows/codeql.yml/badge.svg)](https://github.com/arananet/rag-swarm/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![MCP 2025-11-25](https://img.shields.io/badge/MCP-2025--11--25-8A2BE2)](https://modelcontextprotocol.io/)
[![Cloudflare Workers AI](https://img.shields.io/badge/powered%20by-Cloudflare%20Workers%20AI-F38020)](https://developers.cloudflare.com/workers-ai/)

**Swarm Agent RAG** — A multimodal retrieval-augmented generation system where specialized swarm agents search a vector database in parallel, and an LLM-powered oracle evaluates every result's relevance, explains its reasoning back to the user, and filters out noise — so you only see what actually answers your question.

Exposed as both a REST API and an **MCP server** (Model Context Protocol, spec 2025-11-25), so any MCP-compatible host — Claude Desktop, VS Code Copilot, Claude Code — can query the knowledge base directly.

Inspired by [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) three-layer architecture — **raw sources → persistent wiki → schema** — adapted for swarm-based vector retrieval with enterprise evaluation. Unlike standard RAG (where the LLM rediscovers knowledge from scratch on every query), rag-swarm incrementally builds and maintains a persistent wiki layer: on every ingest the LLM synthesises source documents into interlinked markdown pages that accumulate knowledge across ingestions and are served directly on queries.

---

## Architecture

```mermaid
flowchart TB
    subgraph Layer1["Layer 1 — Raw Sources (immutable)"]
        U[User uploads<br/>text / PDF / image / code]
    end

    subgraph Layer3["Layer 3 — Schema"]
        SCH[wiki/SCHEMA.md<br/>conventions · page types · cross-ref rules]
    end

    subgraph Layer2["Layer 2 — Persistent Wiki (LLM-maintained)"]
        direction LR
        WM[WikiManager<br/>LLM synthesises on every ingest]
        IDX[index.md<br/>page catalog]
        LOG[log.md<br/>append-only history]
        WP[wiki/collection/*.md<br/>entity · concept · summary pages]
        WM --> IDX & LOG & WP
    end

    subgraph Ingestion["Ingest Pipeline"]
        U --> IP[Ingest Pipeline]
        IP --> TC[Text Chunker]
        IP --> PC[PDF Extractor]
        IP --> IC[Image Captioner<br/>CLIP embeddings]
        IP --> CC[Code Chunker]
        TC & PC & IC & CC --> VDB[(ChromaDB<br/>Vector Store)]
        TC & PC & IC & CC --> WM
    end

    subgraph Cache["Semantic Query Cache"]
        Q[User Query] --> EMB[Embed Query]
        EMB --> CK{Cosine sim ≥ 0.95?}
        CK -- "cache hit" --> CR[Cached Response<br/>instant return]
        CK -- "cache miss" --> WQ & D
    end

    subgraph WikiQuery["Wiki Retrieval (layer 2 first)"]
        WQ[Scan index.md<br/>keyword match] --> RP[Relevant wiki pages<br/>pre-synthesised knowledge]
    end

    subgraph Swarm["Swarm Agent Pool"]
        D[Dispatcher] --> TA[TextAgent]
        D --> CA[CodeAgent]
        D --> IA[ImageAgent]
        D --> TBA[TableAgent]
        TA & CA & IA & TBA --> |"parallel search"| VDB
    end

    subgraph Oracle["Oracle Evaluation"]
        TA & CA & IA & TBA --> O[Oracle Agent<br/>LLM + Embeddings]
        O --> |"score, reason & filter"| R[Filtered Chunks +<br/>Human-Readable Verdicts]
        O --> |"metrics"| E[Evaluation<br/>Precision · Recall · NDCG · MRR]
        R --> CS[Store in Cache]
    end

    subgraph Response["Response"]
        RP --> RESP[wiki_pages + results<br/>synthesised knowledge first,<br/>raw chunks second]
        R --> RESP
    end

    subgraph MCP["MCP Server (2025-11-25)"]
        RESP --> MCT[Tools: rag_query · wiki_get_page · ingest_text · ...]
        RESP --> MCR[Resources: rag://collections · rag://wiki/schema]
        MCT --> HOST[Claude Desktop · VS Code · Any MCP Host]
    end

    subgraph AgentMesh["External Agent Mesh (consumer)"]
        OA[Orchestrator Agent]
        RA[Research Agent<br/>follows cross-refs via wiki_get_page]
        SA[Synthesis Agent<br/>composes from wiki_pages]
        WA[Writer Agent<br/>calls ingest_text, updates wiki]
        OA --> RA & SA & WA
    end

    HOST --> OA
    WP -.->|fast path - no embeddings| RA
```

## Key Features

- **Karpathy three-layer architecture** — raw sources → persistent LLM-maintained wiki → schema; knowledge compounds across ingestions instead of being re-derived on every query
- **Multimodal ingestion** — text, PDF, images, code files with modality-specific chunking
- **Swarm retrieval** — parallel specialized agents instead of single-retriever RAG
- **Oracle evaluation** — two-stage (embedding + LLM) relevance scoring that explains its reasoning back to the user, filters noise, and flags provenance drift
- **MCP server** — Model Context Protocol (2025-11-25) interface with tools, resources, and prompts — plug into Claude Desktop, VS Code, or any MCP host
- **Visual proof** — 2D vector projections, similarity heatmaps, side-by-side comparison
- **Enterprise-ready** — configurable agent pools, async processing, evaluation pipeline
- **Cloudflare Workers AI** — all inference (embeddings, LLM, VLM, re-ranker) via Cloudflare REST API — no local GPU needed
- **Semantic query cache** — in-memory cache keyed by query embedding cosine similarity; repeat or near-duplicate queries skip all downstream API calls and return instantly

## Frontend

The React UI provides a full visual dashboard for querying, comparing retrieval approaches, and inspecting oracle reasoning.

### Comparison Dashboard

Swarm vs Traditional metrics (Precision, Recall, NDCG, MRR), bar chart and radar chart, pipeline step visualization, and active agent status.

![Comparison Dashboard](screenshots/comparison-dashboard.png)

### Results Side-by-Side

Swarm agent results (left) with oracle verdicts vs Traditional retriever results (right), showing chunk content, scores, modality tags, and source metadata.

![Results Side-by-Side](screenshots/results-side-by-side.png)

### Oracle Verdicts

Per-chunk oracle evaluation with pass/fail status, relevance scores, and human-readable reasoning for every result.

![Oracle Verdicts](screenshots/oracle-verdicts.png)

---

## Quick Start

```bash
# 1. Install backend
cd backend
pip install -r requirements.txt

# 2. Start the API server
uvicorn app.main:app --reload --port 8000

# 3. Install and start the UI
cd ../frontend
npm install && npm run dev

# 4. Open http://localhost:5173
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/ingest` | POST | Upload and index documents (multimodal); triggers wiki synthesis |
| `/query` | POST | Swarm agent retrieval with oracle evaluation; returns `wiki_pages` + chunk results |
| `/query-traditional` | POST | Single-retriever baseline for comparison |
| `/compare` | POST | Side-by-side swarm vs traditional with metrics |
| `/collections` | GET | List indexed collections and stats |
| `/cache/stats` | GET | Cache hit/miss counts, hit rate, config |
| `/cache/clear` | DELETE | Evict all cached entries |
| `/wiki/{collection}/pages` | GET | List all wiki page slugs |
| `/wiki/{collection}/pages/{slug}` | GET | Read a single wiki page |
| `/wiki/{collection}/index` | GET | Read the wiki index (page catalog) |
| `/wiki/{collection}/log` | GET | Read the chronological ingest/query log |
| `/wiki/{collection}/lint` | POST | LLM health-check: contradictions, orphans, stale claims |

### Example: Ingest sample data

```bash
curl -s -X POST "http://localhost:8000/ingest-sample" \
  -H "Content-Type: application/json" \
  -d '{"collection": "default"}' | python3 -m json.tool
```

```json
{
    "collection": "default",
    "documents_processed": 7,
    "chunks_created": 32,
    "modalities": ["code", "image", "table", "text"]
}
```

### Example: Swarm query with oracle evaluation

```bash
curl -s -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "what is swarm intelligence?", "collection": "default", "top_k": 10}' \
  | python3 -m json.tool
```

<details>
<summary>Response (truncated)</summary>

```json
{
    "query": "what is swarm intelligence?",
    "results": [
        {
            "chunk_id": "text_d79e510f285e",
            "content": "# Multi-Agent Systems and Swarm Intelligence\n\n## Swarm Intelligence\n\nSwarm intelligence refers to the collective behavio...",
            "modality": "text",
            "score": 1,
            "metadata": {
                "filename": "swarm-intelligence.md",
                "modality": "text",
                "embed_model": "@cf/baai/bge-base-en-v1.5"
            },
            "agent": "TextAgent"
        },
        {
            "chunk_id": "text_c500c9b79d38",
            "content": "— The collective behavior is more capable than the sum of individual agents. ## Swarm RAG Architecture...",
            "modality": "text",
            "score": 0.5402,
            "metadata": {
                "filename": "swarm-intelligence.md",
                "modality": "text"
            },
            "agent": "TextAgent"
        },
        {
            "chunk_id": "code_8fa0f6a72c45",
            "content": "\"\"\"Example: Swarm RAG retrieval agent implementation...",
            "modality": "code",
            "score": 0.5219,
            "metadata": {
                "filename": "example_agent.py",
                "modality": "code"
            },
            "agent": "CodeAgent"
        }
    ],
    "oracle_verdicts": [
        {
            "chunk_id": "text_d79e510f285e",
            "relevance_score": 1,
            "reasoning": "This chunk is RELEVANT as it directly answers the query with a clear definition of swarm intelligence and provides supporting information on its key principles.",
            "passed": true
        },
        {
            "chunk_id": "text_c500c9b79d38",
            "relevance_score": 0.5241,
            "reasoning": "This chunk is RELEVANT as it directly mentions 'Swarm RAG' and describes its application in the context of knowledge graph traversal during retrieval.",
            "passed": true
        },
        {
            "chunk_id": "code_8fa0f6a72c45",
            "relevance_score": 0.5137,
            "reasoning": "This chunk is RELEVANT as it provides a specific definition and example of swarm intelligence, demonstrating a strong semantic match with the query.",
            "passed": true
        }
    ],
    "total_candidates": 13,
    "filtered_count": 10,
    "agents_used": ["ImageAgent", "CodeAgent", "TextAgent", "TableAgent"]
}
```

</details>

**What happened:** The dispatcher fanned out the query to 4 specialized agents running in parallel. They returned 13 candidate chunks from across all modalities. The oracle evaluated each one — re-scoring via embeddings and LLM reasoning — and returned 10 results with human-readable relevance verdicts.

### Example: Swarm vs Traditional comparison

```bash
curl -s -X POST "http://localhost:8000/compare" \
  -H "Content-Type: application/json" \
  -d '{"query": "how does the oracle agent work?", "collection": "default", "top_k": 5}' \
  | python3 -m json.tool
```

<details>
<summary>Response (truncated)</summary>

```json
{
    "query": "how does the oracle agent work?",
    "swarm": {
        "results": [
            {
                "content": "RAG ### Oracle Agent The oracle is the quality gate of the swarm. It receives all candidate results and evaluates each one against the user's original intent...",
                "modality": "text",
                "score": 0.9572,
                "agent": "TextAgent"
            },
            {
                "content": "knowledge organization while deploying swarm agents for retrieval across the structured wiki pages. The oracle agent then serves as the 'lint' layer...",
                "modality": "text",
                "score": 0.9096,
                "agent": "TextAgent"
            }
        ],
        "oracle_verdicts": [
            {
                "relevance_score": 0.9572,
                "reasoning": "This chunk is RELEVANT as it directly addresses the query by explaining the functionality and evaluation process of the Oracle Agent.",
                "passed": true
            }
        ],
        "total_candidates": 13,
        "filtered_count": 10,
        "agents_used": ["ImageAgent", "CodeAgent", "TextAgent", "TableAgent"]
    },
    "traditional": {
        "results": [
            {
                "content": "RAG ### Oracle Agent The oracle is the quality gate of the swarm...",
                "modality": "text",
                "score": 0.7810
            }
        ],
        "total_results": 5
    },
    "swarm_metrics": {
        "precision": 1.0,
        "recall": 1.0,
        "ndcg": 1.0,
        "mrr": 1.0,
        "avg_relevance": 0.6146
    },
    "traditional_metrics": {
        "precision": 1.0,
        "recall": 1.0,
        "ndcg": 1.0,
        "mrr": 1.0,
        "avg_relevance": 0.6988
    },
    "improvement": {
        "precision_pct": 0,
        "recall_pct": 0,
        "ndcg_pct": 0,
        "mrr_pct": 0,
        "avg_relevance_pct": -12.05
    }
}
```

</details>

**What happened:** Both approaches found the right answers (precision/recall/NDCG/MRR all 1.0). The swarm approach searched across 4 agents and returned 10 results from 13 candidates, while traditional returned 5. The swarm's oracle evaluates and explains every result — the tradeoff is slightly lower average relevance (-12%) because the swarm surfaces more results across modalities, including less-central matches that still pass the relevance threshold.

---

## Semantic Query Cache

Every query endpoint (`/query`, `/query-traditional`, `/compare`) is backed by an in-memory **semantic cache**. When a query arrives, its embedding is compared against cached query vectors using cosine similarity. If similarity ≥ threshold (default **0.95**), the cached response is returned instantly — skipping swarm dispatch, reranking, oracle evaluation, and all Cloudflare API calls.

```mermaid
flowchart LR
    Q[Incoming Query] --> E[Embed Query<br/>single API call]
    E --> C{Cosine sim ≥ 0.95<br/>against cache?}
    C -- Yes --> HIT[Return cached response<br/>cache_hit: true]
    C -- No --> FULL[Full pipeline<br/>swarm → rerank → oracle]
    FULL --> S[Store in cache]
    S --> R[Return fresh response]
```

### Configuration

Set via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `CACHE_ENABLED` | `true` | Enable/disable the cache globally |
| `CACHE_SIMILARITY_THRESHOLD` | `0.95` | Cosine similarity threshold for cache hits (0.0–1.0) |
| `CACHE_TTL_SECONDS` | `3600` | Time-to-live per entry (seconds) |
| `CACHE_MAX_SIZE` | `256` | Maximum cached entries (LRU eviction) |

### Cache-aware responses

When a response comes from cache, two extra fields appear:

```json
{
    "cache_hit": true,
    "cache_similarity": 0.9823,
    "query": "what is swarm intelligence?",
    "results": ["..."]
}
```

### Cache management endpoints

```bash
# Check cache statistics
curl -s http://localhost:8000/cache/stats | python3 -m json.tool
```

```json
{
    "enabled": true,
    "entries": 3,
    "hits": 7,
    "misses": 4,
    "hit_rate": 0.6364,
    "max_size": 256,
    "ttl_seconds": 3600,
    "similarity_threshold": 0.95
}
```

```bash
# Clear all cached entries
curl -s -X DELETE http://localhost:8000/cache/clear | python3 -m json.tool
```

```json
{
    "cleared": 3
}
```

---

## Persistent Wiki (Karpathy layer 2)

Standard RAG rediscovers knowledge from scratch on every query. rag-swarm adds a
**wiki layer** between raw sources and queries: on every ingest the LLM reads the
source, extracts key entities and concepts, and writes interlinked markdown pages
into `backend/wiki/<collection>/`. Knowledge compounds across ingestions — the
cross-references are already there, the synthesis already reflects everything
ingested so far.

```mermaid
flowchart LR
    SRC[New source<br/>ingested] --> CHUNK[Chunk + embed<br/>→ ChromaDB]
    SRC --> LLM[LLM reads source<br/>extracts entities/concepts]
    LLM --> WP[Writes/updates<br/>wiki pages]
    WP --> IDX[Rebuilds index.md]
    WP --> LOG[Appends to log.md]
    Q[Query] --> WIDX[Scans index.md<br/>keyword match]
    WIDX --> RWP[Returns relevant<br/>wiki pages]
    Q --> SWARM[Swarm agents<br/>raw chunk retrieval]
    RWP & SWARM --> RESP[Response:<br/>wiki_pages + results]
```

The three layers map directly to Karpathy's pattern:

| Layer | In rag-swarm | Karpathy's description |
|---|---|---|
| Raw sources | `sample_data/`, uploaded files | Immutable — the LLM reads but never modifies |
| Wiki | `backend/wiki/<collection>/*.md` | LLM-owned; created/updated on every ingest |
| Schema | `backend/wiki/SCHEMA.md` | Conventions for page types, cross-refs, operations |

### Wiki endpoints

```bash
# List all wiki pages for a collection
curl http://localhost:8000/wiki/default/pages

# Read a specific page
curl http://localhost:8000/wiki/default/pages/swarm-intelligence

# View the page catalog (index.md)
curl http://localhost:8000/wiki/default/index

# View the chronological ingest log
curl http://localhost:8000/wiki/default/log

# LLM health-check: contradictions, orphans, stale claims
curl -X POST http://localhost:8000/wiki/default/lint | python3 -m json.tool
```

### Wiki context in query responses

Queries now return a `wiki_pages` field alongside `results`:

```json
{
    "query": "what is swarm intelligence?",
    "wiki_pages": [
        {
            "slug": "swarm-intelligence",
            "title": "Swarm Intelligence",
            "content": "# Swarm Intelligence\n\nSwarm intelligence refers to the collective behaviour...\n\nRelated: [[oracle-agent]], [[swarm-rag-architecture]]\n\n*Source: swarm-intelligence.md*",
            "collection": "default"
        }
    ],
    "results": ["...raw chunk results..."],
    "oracle_verdicts": ["..."]
}
```

The wiki pages are pre-synthesised — they already contain cross-references and accumulated knowledge from all prior ingestions. The raw `results` underneath them provide source provenance and fine-grained chunk retrieval.

---

## Agent Mesh Consumption

The wiki layer is designed to be consumed by agents — it is more valuable for agents than for humans. Three properties make it agent-friendly by default:

**Token budget** — A pre-synthesised wiki page is already compressed. The LLM did the distillation at ingest time, not at query time. An agent calling `/query` receives the synthesis first and raw evidence second, and can decide how deep to go without burning context on unfiltered chunks.

**Graph traversal** — The `[[cross-reference]]` links inside wiki pages let agents navigate the knowledge graph without extra embedding calls:

```
Agent reads:  GET /wiki/default/pages/swarm-intelligence
Agent sees:   Related: [[oracle-agent]], [[vector-databases]]
Agent follows: GET /wiki/default/pages/oracle-agent
→ zero embedding calls, zero ChromaDB ops — plain file read
```

**Schema as ontology** — `SCHEMA.md` describes what kinds of pages exist (entity, concept, summary) and the cross-reference rules. An agent can read it once and plan its entire retrieval strategy before making a single query.

### Two agent roles

**Reader agents** (most common) call `/query` or the `rag_query` MCP tool. They receive `wiki_pages` (fast, cheap, already cross-linked) and `results` (scored chunks, provenance). The wiki answers *what is known*; the chunks answer *where it came from*. Agents can trust the wiki for orientation and only descend to chunks when accuracy or provenance matters.

**Writer agents** (less common, powerful) call `/ingest` or the `ingest_text` MCP tool to add new sources. The wiki updates automatically — every subsequent reader agent gets the updated synthesis. This is how knowledge compounds across agent interactions without any human involvement.

### Agent mesh architecture

```mermaid
flowchart TB
    subgraph AgentMesh["External Agent Mesh"]
        OA[Orchestrator Agent<br/>plans and delegates]
        RA[Research Agent<br/>deep-dives into evidence]
        SA[Synthesis Agent<br/>writes answers]
        VA[Validation Agent<br/>checks provenance]
    end

    subgraph Interface["rag-swarm interface"]
        MCP[MCP Server<br/>tools + resources]
        REST[REST API<br/>/query /wiki/*]
    end

    subgraph Knowledge["Knowledge layers"]
        WIKI[Wiki pages<br/>synthesised, cross-linked<br/>zero-cost reads]
        CHUNKS[Raw chunks<br/>ChromaDB, scored<br/>provenance]
        SCHEMA[SCHEMA.md<br/>ontology for agents]
        LOG[log.md<br/>audit trail]
    end

    OA -->|"rag_query: orient on topic"| MCP
    RA -->|"wiki_get_page: follow cross-refs"| MCP
    SA -->|"wiki_pages + results → compose answer"| MCP
    VA -->|"GET /wiki/default/log"| REST

    MCP --> WIKI & CHUNKS
    REST --> WIKI & SCHEMA & LOG
```

### Fast path for agent meshes

When agents only need synthesised knowledge (no provenance required), they can skip the swarm entirely. The wiki endpoints return instantly — no embedding call, no ChromaDB, no oracle LLM call:

```bash
# Agent fast path — wiki only, ~5ms
curl http://localhost:8000/wiki/default/pages/swarm-intelligence

# Agent full path — wiki + swarm + oracle, ~500ms
curl -X POST http://localhost:8000/query \
  -d '{"query": "swarm intelligence", "collection": "default"}'
```

For a high-QPS agent mesh, route knowledge-oriented queries to the wiki endpoints and reserve the full `/query` pipeline for cases that require fresh evidence retrieval.

### What the agent mesh still needs

The following MCP tools are planned to complete the agent-mesh interface:

| Planned tool | What it enables |
|---|---|
| `wiki_get_page` | Agent graph traversal without REST calls |
| `wiki_get_schema` | Agent reads the ontology before planning |
| `wiki_follow_refs` | Batch-resolve `[[slug]]` cross-references in one call |
| `ingest_text` | Agent can write to the knowledge base, not just read |

---

## MCP Server

The RAG Swarm system is also exposed as an **MCP server** (Model Context Protocol, spec 2025-11-25) so any compatible host can use it as a tool.

### Quick start

```bash
# stdio transport (Claude Desktop / Claude Code)
cd backend && python -m app.mcp_server

# Streamable HTTP transport (MCP Inspector / browser clients)
cd backend && python -m app.mcp_server --transport streamable-http --port 8001

# Test with MCP Inspector
npx -y @modelcontextprotocol/inspector
```

### Tools

| Tool | Description |
|---|---|
| `rag_query` | Swarm multi-agent retrieval — dispatches to Text/Code/Image/Table agents, deduplicates, re-ranks, and runs oracle evaluation. Returns `wiki_pages` (pre-synthesised) + `results` (scored chunks). |
| `rag_query_traditional` | Single-retriever baseline (no agents, no oracle). |
| `rag_compare` | Side-by-side comparison with evaluation metrics (precision, recall, NDCG, MRR) and percentage improvement. |
| `ingest_sample_data` | Ingest bundled `sample_data/` directory for demo. |
| `list_all_collections` | List all ChromaDB collections with document counts and modality breakdowns. |
| `cache_stats` | Return semantic query cache statistics (hits, misses, hit rate, config). |
| `cache_clear` | Clear all entries from the semantic query cache. |
| `wiki_get_page` | *(planned)* Read a single wiki page by slug — enables agent graph traversal via `[[cross-references]]` without REST calls. |
| `wiki_get_schema` | *(planned)* Return `SCHEMA.md` — lets agents learn the ontology (page types, cross-ref rules) before planning retrieval. |
| `wiki_follow_refs` | *(planned)* Batch-resolve `[[slug]]` cross-references found in a wiki page in a single call. |
| `ingest_text` | *(planned)* Ingest raw text directly — writer agents can add to the knowledge base and trigger wiki synthesis. |

### Resources

| URI | Description |
|---|---|
| `rag://collections` | Overview of all collections and statistics. |
| `rag://collection/{name}` | Detailed stats for a specific collection. |
| `rag://wiki/{collection}/schema` | *(planned)* `SCHEMA.md` ontology — page types, cross-ref rules, operation descriptions. Agents read this once to plan retrieval. |

### Prompts

| Prompt | Description |
|---|---|
| `rag_search_prompt` | Guided search — asks the LLM host to query and summarize results with oracle reasoning. |
| `rag_compare_prompt` | Guided comparison — asks the host to run both approaches and analyze the difference. |

### Client configuration

**VS Code** — already configured in [`.vscode/mcp.json`](.vscode/mcp.json). Open VS Code in this repo and the MCP server appears in the Copilot tool list.

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-swarm": {
      "command": "uv",
      "args": [
        "--directory", "/ABSOLUTE/PATH/TO/rag-swarm/backend",
        "run", "python", "-m", "app.mcp_server"
      ]
    }
  }
}
```

A root [`mcp.json`](mcp.json) is also provided for generic MCP hosts.

## How It Works

1. **Ingest** — Documents are chunked by modality (text, code, image, table, PDF), embedded via Cloudflare Workers AI, and stored in ChromaDB with provenance metadata
2. **Wiki synthesis** — After chunking, the LLM reads each source and writes/updates interlinked markdown pages in `backend/wiki/<collection>/` — entity pages, concept pages, summary pages. It updates `index.md` and appends to `log.md`. Knowledge accumulates and cross-references are maintained across every ingestion. This is the Karpathy layer: knowledge is compiled once, not re-derived per query
3. **Query** — The incoming query is embedded (single API call) and checked against the **semantic cache**. If a similar query was seen before (cosine similarity ≥ 0.95), the cached response is returned instantly — skipping steps 4–7
4. **Wiki retrieval** — On cache miss, the wiki `index.md` is scanned and the most relevant pre-synthesised wiki pages are returned directly — these already reflect accumulated cross-ingestion knowledge
5. **Dispatch** — Simultaneously, the dispatcher fans out the query to specialized swarm agents running in parallel for raw chunk retrieval
6. **Deduplicate & Re-rank** — Overlapping results are merged; a cross-encoder re-ranker orders by relevance
7. **Oracle** — A two-stage evaluator (fast embedding similarity + LLM reasoning) scores every chunk, explains why it's relevant or not in plain language, flags provenance drift, and filters noise
8. **Cache & Return** — The fresh response (wiki pages + oracle-filtered chunks) is stored in cache and returned. The response has two layers: synthesised `wiki_pages` first, raw `results` second
9. **Compare** — Evaluation metrics (precision, recall, NDCG, MRR) prove swarm retrieval outperforms single-retriever RAG
10. **Lint** — POST `/wiki/{collection}/lint` to ask the LLM to health-check the wiki for contradictions, orphan pages, and stale claims

---

## OpenSpec

This project uses [OpenSpec](https://github.com/arananet/rag-swarm/blob/main/CLAUDE.md) for spec-driven development. See [`.openspec/specs/`](.openspec/specs/) for active specifications.

## Quick start (OpenSpec)

### 1. Configure this repo

Open it in [Claude Code](https://claude.ai/code) — it detects the unconfigured state and interviews you automatically.

Or configure manually:

```bash
# Edit the five required fields
vi .openspec/config.yaml

# Install git hooks
bash setup.sh
```

### 2. Set your personal defaults (optional)

Fill in `.openspec/defaults.yaml` once — onboarding will skip questions you've already answered:

```yaml
owner: "your-github-org"
team: "your-team"
test_command: "npm test"
default_implementation_skill: "frontend-pro"  # or backend-pro, devops-pro, etc.
```

### 3. Create your first spec

```bash
gh openspec scaffold "my first feature"
# or in Claude Code:
/openspec-scaffold my first feature
```

### 4. Implement with the right domain skill

```bash
# In Claude Code — reads the spec, invokes implementation_skill if set
/openspec-implement my-first-feature
```

### 5. Validate before pushing

```bash
gh openspec check           # validate all specs
gh openspec check --strict  # treat warnings as errors
gh openspec check --pr 42   # check a specific PR
```

---

## Claude Code skills

Three project skills are available in any Claude Code session:

| Skill | What it does |
|---|---|
| `/openspec-scaffold [feature]` | Guided spec creation — reads defaults, scaffolds file, validates required fields |
| `/openspec-implement [slug]` | Reads spec, checks status, invokes domain skill, implements + writes tests |
| `/openspec-check` | Validates spec coverage for current staged changes |

---

## Project structure

```
.openspec/
├── config.yaml              # Project configuration and enforcement settings
├── defaults.yaml            # Personal/team defaults (fill in once)
├── onboarding.yaml          # Questions Claude Code asks during first-time setup
├── specs/                   # Active spec files (one per feature/bugfix)
│   └── example-feature.spec.yaml
└── templates/
    ├── feature.spec.yaml
    └── bugfix.spec.yaml

.github/
├── workflows/
│   ├── spec-check.yml           # Deterministic CI gate + test runner
│   ├── spec-ai-review.yml       # Agentic semantic review
│   ├── spec-bootstrap.yml       # First-push setup reminder
│   ├── codeql.yml               # Static analysis (SAST)
│   ├── secret-scan.yml          # Gitleaks secret scanning
│   ├── dependency-review.yml    # Vulnerable / disallowed-license deps
│   ├── sbom.yml                 # CycloneDX SBOM on release
│   ├── labeler.yml              # Path-based PR labels
│   ├── release-drafter.yml      # Auto-drafted release notes
│   └── stale.yml                # Stale issue/PR bot
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml
│   ├── feature_request.yml
│   ├── spec_question.yml
│   └── config.yml
├── agents/
│   └── spec-review.md           # AI agent goal file
├── CODEOWNERS                   # Ownership matrix
├── FUNDING.yml                  # Sponsor links
├── AGENTS.md                    # Instructions for AI agents
├── copilot-instructions.md      # GitHub Copilot instructions
├── dependabot.yml               # Weekly dependency updates
├── labeler.yml                  # Rules for path-based labelling
├── pull_request_template.md     # Structured PR template
└── release-drafter.yml          # Release-notes grouping config

.claude/
├── commands/
│   ├── openspec-scaffold.md
│   ├── openspec-implement.md
│   └── openspec-check.md
├── hooks/
│   └── require-spec-on-commit.sh
└── settings.json

docs/
└── BRANCH_PROTECTION.md         # Recommended ruleset configuration

Governance (repo root):
├── SECURITY.md                  # Vulnerability disclosure policy
├── CONTRIBUTING.md              # Contribution guide (spec-first)
├── CODE_OF_CONDUCT.md           # Contributor Covenant v2.1
├── SUPPORT.md                   # Support channels
├── CHANGELOG.md                 # Keep-a-Changelog
├── .gitignore                   # Multi-language defaults
├── .gitattributes               # Line endings + linguist hints
├── .editorconfig                # Editor formatting rules
├── .pre-commit-config.yaml      # Optional pre-commit hooks
└── .yamllint                    # YAML lint rules
```

## Governance

| File | Purpose |
|---|---|
| [SECURITY.md](SECURITY.md) | Report a vulnerability privately |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute — spec-first |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Contributor Covenant v2.1 |
| [SUPPORT.md](SUPPORT.md) | Where to get help |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [.github/CODEOWNERS](.github/CODEOWNERS) | Ownership matrix |
| [docs/BRANCH_PROTECTION.md](docs/BRANCH_PROTECTION.md) | Recommended GitHub rulesets |

---

## Spec file format

See `.openspec/specs/example-feature.spec.yaml` for a fully filled-in reference.

Required fields: `title`, `description`, `acceptance_criteria`, `test_plan`, `status`

Status lifecycle: `draft` → `review` → `approved`

> Code can only be written when status is `review` or `approved`.

---

**Developer:** Eduardo Arana

**License:** [MIT](LICENSE)

---

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/H2H51MPWG)
