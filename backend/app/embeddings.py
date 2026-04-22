"""Embedding engine — Cloudflare Workers AI for text embeddings and LLM inference."""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import httpx
from dotenv import load_dotenv

load_dotenv()

# Cloudflare Workers AI configuration
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run"

# Model identifiers
EMBEDDING_MODEL = "@cf/baai/bge-base-en-v1.5"          # 768-dim text embeddings
LLM_MODEL = "@cf/meta/llama-3.1-8b-instruct"           # Text generation / Oracle
VLM_MODEL = "@cf/llava-hf/llava-1.5-7b-hf"             # Image-to-text captioning
RERANKER_MODEL = "@cf/baai/bge-reranker-base"           # Re-ranking pairs

EMBEDDING_DIM = 768
_MAX_BATCH = 100  # Cloudflare batch limit per request
_TIMEOUT = 30.0


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {CF_API_TOKEN}"}


def _cf_url(model: str) -> str:
    return f"{CF_BASE_URL}/{model}"


# ---------- Text Embeddings via Cloudflare Workers AI ----------


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings via Cloudflare Workers AI BGE model."""
    if not texts:
        return []
    all_embeddings: list[list[float]] = []
    # Batch in chunks of _MAX_BATCH
    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i : i + _MAX_BATCH]
        resp = httpx.post(
            _cf_url(EMBEDDING_MODEL),
            headers=_headers(),
            json={"text": batch},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        vectors = data.get("result", {}).get("data", [])
        all_embeddings.extend(vectors)
    return all_embeddings


def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    return embed_texts([text])[0]


# ---------- LLM Inference via Cloudflare Workers AI ----------


def llm_generate(prompt: str, max_tokens: int = 512) -> str:
    """Generate text using Cloudflare Workers AI LLM."""
    resp = httpx.post(
        _cf_url(LLM_MODEL),
        headers=_headers(),
        json={
            "prompt": prompt,
            "max_tokens": max_tokens,
        },
        timeout=_TIMEOUT * 2,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("response", "")


def llm_chat(messages: list[dict], max_tokens: int = 512) -> str:
    """Chat-style LLM inference with system/user/assistant messages."""
    resp = httpx.post(
        _cf_url(LLM_MODEL),
        headers=_headers(),
        json={
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=_TIMEOUT * 2,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("response", "")


# ---------- Image Captioning via Cloudflare Workers AI VLM ----------


def caption_image(image_b64: str, prompt: str = "Describe this image in detail.") -> str:
    """Generate a caption for a base64-encoded image using the VLM."""
    resp = httpx.post(
        _cf_url(VLM_MODEL),
        headers=_headers(),
        json={
            "image": image_b64,
            "prompt": prompt,
            "max_tokens": 256,
        },
        timeout=_TIMEOUT * 2,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("description", "")


# ---------- Re-ranking via Cloudflare Workers AI ----------


def rerank_pairs(query: str, passages: list[str]) -> list[float]:
    """Score query-passage relevance pairs using the BGE re-ranker.

    Returns a list of relevance scores (one per passage), values in [0,1].
    """
    if not passages:
        return []
    # The re-ranker takes pairs of (query, passage) and returns similarity scores
    resp = httpx.post(
        _cf_url(RERANKER_MODEL),
        headers=_headers(),
        json={"text": query, "text_pair": passages},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    # bge-reranker-base returns list of {label, score} dicts
    results = data.get("result", [])
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return [r.get("score", 0.0) for r in results]
    return [0.0] * len(passages)


# ---------- Utilities ----------


def chunk_id(content: str, modality: str, index: int) -> str:
    """Generate a deterministic chunk ID."""
    h = hashlib.sha256(f"{modality}:{index}:{content[:200]}".encode()).hexdigest()[:12]
    return f"{modality}_{h}"


@lru_cache(maxsize=1)
def embedding_dimension() -> int:
    """Return the dimension of the embedding model."""
    return EMBEDDING_DIM
