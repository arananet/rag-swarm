# Vector Databases and Embeddings

## What Are Embeddings?

Embeddings are dense numerical vector representations of data (text, images, audio) that capture semantic meaning in a continuous vector space. Similar concepts are mapped to nearby points, enabling mathematical comparison of meaning.

### Text Embedding Models

- **all-MiniLM-L6-v2** — 384 dimensions, fast, good for general-purpose text similarity
- **text-embedding-3-large** (OpenAI) — 3072 dimensions, state-of-the-art quality
- **BGE-M3** (BAAI) — Multi-lingual, multi-granularity embeddings
- **Cohere embed-v3** — Optimized for retrieval with compression support

### Image Embedding Models

- **CLIP (ViT-B/32)** — Joint text-image embedding space, enables cross-modal search
- **SigLIP** — Improved CLIP variant with sigmoid loss
- **DINOv2** — Self-supervised visual features, no text alignment

## Vector Databases

| Database | Type | Key Features |
|---|---|---|
| ChromaDB | Embedded / Client-Server | Python-native, simple API, good for prototyping |
| Pinecone | Managed Cloud | Serverless, auto-scaling, metadata filtering |
| Weaviate | Self-hosted / Cloud | GraphQL API, hybrid search, multi-modal |
| Qdrant | Self-hosted / Cloud | Rust-based, fast, rich filtering |
| Milvus | Self-hosted | Distributed, GPU-accelerated, massive scale |
| pgvector | PostgreSQL Extension | SQL integration, ACID transactions |

## Similarity Metrics

- **Cosine Similarity** — Measures angle between vectors. Range: [-1, 1]. Most common for text.
- **Euclidean Distance** — Measures straight-line distance. Good for normalized embeddings.
- **Dot Product** — Measures magnitude-weighted similarity. Fast but sensitive to vector norms.

## Chunking Strategies

Chunking is how documents are split before embedding. Strategy matters enormously:

1. **Fixed-size** — Split every N characters/tokens. Simple but loses context.
2. **Sentence-based** — Split at sentence boundaries. Better semantic units.
3. **Semantic chunking** — Use embedding similarity to find natural breakpoints.
4. **Document-structure** — Split by headers, paragraphs, code blocks. Best for structured docs.
5. **Recursive** — Hierarchical splitting with fallback strategies.

For multimodal RAG, each modality needs its own chunking strategy:
- **Text**: Sentence or paragraph-based
- **Code**: Function/class-level splitting
- **Tables**: Row groups or entire tables as units
- **Images**: Whole image + caption/description as a single chunk
