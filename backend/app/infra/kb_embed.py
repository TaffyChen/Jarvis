"""向量化：优先 OpenAI 兼容 embedding，否则 hashing（固定 384 维）。"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from app.config import settings
from app.infra.kb_chunk import _tokens

HASH_DIM = 384


def embedding_info() -> dict[str, Any]:
    backend = (settings.embedding_backend or "hash").strip().lower() or "hash"
    if backend == "openai" and (settings.embedding_api_key or settings.llm_api_key):
        return {
            "backend": "openai",
            "model": settings.embedding_model or "text-embedding-3-small",
            "dim": int(settings.embedding_dim or 1536),
            "baseUrl": (settings.embedding_base_url or settings.llm_base_url or "").rstrip("/"),
        }
    return {"backend": "hash", "model": "ngram-hash", "dim": HASH_DIM}


def embed_dim() -> int:
    return int(embedding_info()["dim"])


def _hash_embed(text: str, dim: int = HASH_DIM) -> list[float]:
    toks = _tokens(text or "")
    v = np.zeros(dim, dtype=np.float32)
    for t in toks:
        h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 16) & 1) else -1.0
        v[idx] += sign
    n = float(np.linalg.norm(v))
    if n > 0:
        v /= n
    return v.tolist()


def _openai_embed(texts: list[str]) -> list[list[float]]:
    import httpx

    info = embedding_info()
    url = info["baseUrl"].rstrip("/") + "/embeddings"
    key = (settings.embedding_api_key or settings.llm_api_key or "").strip()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    out: list[list[float]] = [[] for _ in texts]
    batch = 32
    with httpx.Client(timeout=60.0) as client:
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            r = client.post(url, headers=headers, json={"model": info["model"], "input": chunk})
            r.raise_for_status()
            data = r.json().get("data") or []
            data = sorted(data, key=lambda x: int(x.get("index") or 0))
            for j, row in enumerate(data):
                out[i + j] = list(row.get("embedding") or [])
    if any(not v for v in out):
        raise RuntimeError("embedding response incomplete")
    return out


def embed_texts(texts: list[str]) -> list[list[float]]:
    info = embedding_info()
    if info["backend"] == "openai":
        return _openai_embed(texts)
    return [_hash_embed(t) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text or ""])[0]
