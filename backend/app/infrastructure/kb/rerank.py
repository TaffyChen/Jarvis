"""交叉编码器重排：OpenAI 兼容 /rerank（硅基流动 BGE reranker 等）。"""
from __future__ import annotations

from typing import Any

from app.core.config import settings


def rerank_info() -> dict[str, Any]:
    enabled = bool(settings.rerank_enabled) and bool(
        (settings.rerank_api_key or settings.embedding_api_key or "").strip()
        or ((settings.embedding_backend or "").strip().lower() == "openai" and settings.llm_api_key)
    )
    base = (
        (settings.rerank_base_url or "").strip()
        or (settings.embedding_base_url or "").strip()
        or (settings.llm_base_url or "").strip()
    )
    return {
        "enabled": enabled,
        "model": (settings.rerank_model or "BAAI/bge-reranker-v2-m3").strip(),
        "baseUrl": base.rstrip("/"),
    }


def rerank_hits(query: str, hits: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """按 query 对候选片段重排。失败或未启用时原序截断。"""
    if not hits:
        return []
    n = max(1, int(top_n or 5))
    info = rerank_info()
    if not info["enabled"] or len(hits) == 1 or not (query or "").strip():
        return hits[:n]
    docs = [(h.get("text") or "")[:1800] for h in hits]
    if not any(docs):
        return hits[:n]
    try:
        ranked = _call_rerank(query.strip(), docs, min(n, len(docs)), info)
    except Exception as e:
        print(f"[kb] rerank failed, keep hybrid order: {e}", flush=True)
        return hits[:n]
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in ranked:
        try:
            idx = int(row.get("index"))
        except Exception:
            continue
        if idx < 0 or idx >= len(hits) or idx in seen:
            continue
        seen.add(idx)
        item = dict(hits[idx])
        item["score"] = round(float(row.get("relevance_score") or item.get("score") or 0), 4)
        item["reranked"] = True
        out.append(item)
        if len(out) >= n:
            break
    if not out:
        return hits[:n]
    return out


def _call_rerank(query: str, documents: list[str], top_n: int, info: dict[str, Any]) -> list[dict]:
    import httpx

    key = (
        (settings.rerank_api_key or "").strip()
        or (settings.embedding_api_key or "").strip()
        or (settings.llm_api_key or "").strip()
    )
    url = info["baseUrl"].rstrip("/") + "/rerank"
    payload = {
        "model": info["model"],
        "query": query,
        "documents": documents,
        "top_n": top_n,
        "return_documents": False,
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json() or {}
    return list(data.get("results") or [])
