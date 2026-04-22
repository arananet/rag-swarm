# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is a technique that enhances large language models by grounding their responses in external knowledge. Instead of relying solely on parametric memory (knowledge encoded during training), RAG systems retrieve relevant documents from an external corpus at query time and condition the LLM's generation on those documents.

## Core Architecture

A typical RAG pipeline has three stages:

1. **Indexing** — Documents are chunked, embedded into vector representations, and stored in a vector database (e.g., ChromaDB, Pinecone, Weaviate).
2. **Retrieval** — Given a user query, the system embeds the query and performs approximate nearest neighbor search to find the most relevant chunks.
3. **Generation** — The retrieved chunks are concatenated with the query into a prompt, which is fed to the LLM for answer generation.

## Limitations of Traditional RAG

| Problem | Description |
|---|---|
| Lost in the middle | LLMs struggle with information placed in the middle of long contexts |
| Chunk boundary issues | Relevant information split across chunks may lose context |
| Single-vector bottleneck | One embedding per query may not capture multi-faceted intent |
| No cross-document reasoning | Retrieved chunks are treated independently |
| Stale knowledge | Embeddings must be rebuilt when documents change |

## Advanced RAG Techniques

- **Hypothetical Document Embeddings (HyDE)** — Generate a hypothetical answer first, embed it, and use that embedding for retrieval.
- **Multi-query RAG** — Decompose the user query into sub-queries for broader retrieval.
- **Graph RAG** — Build a knowledge graph from documents and traverse it during retrieval.
- **Swarm RAG** — Use multiple specialized agents to search different aspects of the knowledge base in parallel, with an oracle evaluating result quality.

## Evaluation Metrics

Standard information retrieval metrics apply:

- **Precision@k** — Fraction of top-k results that are relevant
- **Recall@k** — Fraction of relevant documents found in top-k
- **NDCG** — Normalized Discounted Cumulative Gain, accounting for position
- **MRR** — Mean Reciprocal Rank, position of the first relevant result
- **Faithfulness** — Whether the generated answer is supported by retrieved documents
- **Answer Relevancy** — Whether the answer addresses the user's question
