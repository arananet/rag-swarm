"""Embedding engine — Cloudflare Workers AI for text embeddings and LLM inference."""

from __future__ import annotations

import hashlib
import os
import time
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
_MAX_BATCH = 20  # Keep small to avoid CF free-tier rate limits
_TIMEOUT = 30.0
_MAX_RETRIES = 6
_RETRY_BACKOFF = 3.0  # seconds, doubles each retry


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {CF_API_TOKEN}"}


def _cf_url(model: str) -> str:
    return f"{CF_BASE_URL}/{model}"


def _post_with_retry(url: str, json: dict, timeout: float = _TIMEOUT) -> httpx.Response:
    """POST with exponential backoff on 429 rate-limit responses."""
    for attempt in range(_MAX_RETRIES):
        resp = httpx.post(url, headers=_headers(), json=json, timeout=timeout)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        wait = _RETRY_BACKOFF * (2 ** attempt)
        time.sleep(wait)
    resp.raise_for_status()  # raise on final failure
    return resp


# ---------- Text Embeddings via Cloudflare Workers AI ----------


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings via Cloudflare Workers AI BGE model."""
    if not texts:
        return []
    all_embeddings: list[list[float]] = []
    # Batch in chunks of _MAX_BATCH with inter-batch delay
    for i in range(0, len(texts), _MAX_BATCH):
        if i > 0:
            time.sleep(1.0)  # avoid burst rate-limiting
        batch = texts[i : i + _MAX_BATCH]
        resp = _post_with_retry(
            _cf_url(EMBEDDING_MODEL),
            json={"text": batch},
            timeout=_TIMEOUT,
        )
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
    resp = _post_with_retry(
        _cf_url(LLM_MODEL),
        json={
            "prompt": prompt,
            "max_tokens": max_tokens,
        },
        timeout=_TIMEOUT * 2,
    )
    data = resp.json()
    return data.get("result", {}).get("response", "")


def llm_chat(messages: list[dict], max_tokens: int = 512) -> str:
    """Chat-style LLM inference with system/user/assistant messages."""
    resp = _post_with_retry(
        _cf_url(LLM_MODEL),
        json={
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=_TIMEOUT * 2,
    )
    data = resp.json()
    return data.get("result", {}).get("response", "")


# ---------- Image Captioning via Cloudflare Workers AI VLM ----------


def caption_image(image_b64: str, prompt: str = "Describe this image in detail.") -> str:
    """Generate a caption for a base64-encoded image using the VLM."""
    resp = _post_with_retry(
        _cf_url(VLM_MODEL),
        json={
            "image": image_b64,
            "prompt": prompt,
            "max_tokens": 256,
        },
        timeout=_TIMEOUT * 2,
    )
    data = resp.json()
    return data.get("result", {}).get("description", "")


# ---------- Re-ranking via Cloudflare Workers AI ----------


def rerank_pairs(query: str, passages: list[str]) -> list[float]:
    """Score query-passage relevance pairs using the BGE re-ranker.

    Returns a list of relevance scores (one per passage), values in [0,1].
    """
    if not passages:
        return []
    # CF reranker expects: {"query": str, "contexts": [{"text": str}, ...]}
    contexts = [{"text": p} for p in passages]
    resp = _post_with_retry(
        _cf_url(RERANKER_MODEL),
        json={"query": query, "contexts": contexts},
        timeout=_TIMEOUT,
    )
    data = resp.json()
    # Response: {"result": {"response": [{"id": 0, "score": 0.17}, ...]}}
    response_list = data.get("result", {}).get("response", [])
    if response_list:
        # Results may not be in original order — sort by id to align with passages
        score_map = {r["id"]: r.get("score", 0.0) for r in response_list}
        return [score_map.get(i, 0.0) for i in range(len(passages))]
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
