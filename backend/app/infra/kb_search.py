"""混合检索：向量排序 + 关键词排序，RRF 融合。"""
from __future__ import annotations

from typing import Any

from app.infra.kb_chunk import _tokens


def keyword_score(query: str, text: str) -> float:
    q = set(_tokens(query or ""))
    if not q:
        return 0.0
    t = set(_tokens(text or ""))
    if not t:
        return 0.0
    hit = len(q & t)
    return hit / max(1, len(q))


def keyword_rank(query: str, rows: list[dict[str, Any]], top_k: int = 20) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        sc = keyword_score(query, f"{row.get('text') or ''} {row.get('source') or ''}")
        if sc <= 0:
            continue
        item = dict(row)
        item["score"] = round(float(sc), 4)
        scored.append(item)
    scored.sort(key=lambda x: -x["score"])
    return scored[: max(1, int(top_k))]


def rrf_fuse(*rank_lists: list[dict[str, Any]], top_k: int = 5, k: int = 60) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in rank_lists:
        for rank, row in enumerate(rows, start=1):
            key = str(row.get("id") or "")
            if not key:
                continue
            bucket = merged.setdefault(key, {"item": dict(row), "score": 0.0})
            bucket["score"] += 1.0 / (k + rank)
    fused = sorted(merged.values(), key=lambda x: -x["score"])
    out = []
    for row in fused[: max(1, int(top_k))]:
        item = row["item"]
        item["score"] = round(float(row["score"]), 4)
        out.append(item)
    return out
