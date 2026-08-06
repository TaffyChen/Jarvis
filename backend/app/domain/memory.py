"""对话沉淀：纯领域规则，不碰存储。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

_KIND_OK = {"stock", "market", "preference", "error", "insight"}


def normalize_memory_item(item: dict, *, source_question: str = "") -> dict | None:
    if not isinstance(item, dict):
        return None
    content = (item.get("content") or "").strip()
    title = (item.get("title") or "").strip()
    if not content and not title:
        return None
    kind = (item.get("kind") or "insight").strip().lower()
    if kind not in _KIND_OK:
        kind = "insight"
    code = (item.get("code") or "").strip() or None
    tags = item.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    tags = [str(t).strip() for t in tags if str(t).strip()][:8]
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": item.get("id") or f"mem_{uuid.uuid4().hex[:12]}",
        "ts": now,
        "kind": kind,
        "code": code,
        "title": title or content[:40],
        "content": content or title,
        "tags": tags,
        "expiresAt": item.get("expiresAt") or None,
        "sourceQuestion": (source_question or item.get("sourceQuestion") or "")[:200],
        "status": "active",
    }


def rank_memories(notes: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """轻量关键词重叠检索，不依赖向量库。"""
    active = [n for n in notes if n.get("status", "active") == "active"]
    if not active:
        return []
    q = (query or "").lower()
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]{1,2}|[a-z0-9_]{2,}", q))
    scored: list[tuple[float, dict]] = []
    for n in active:
        blob = " ".join(
            [
                str(n.get("title") or ""),
                str(n.get("content") or ""),
                str(n.get("code") or ""),
                " ".join(n.get("tags") or []),
                str(n.get("kind") or ""),
            ]
        ).lower()
        score = 0.0
        if n.get("code") and str(n["code"]).lower() in q:
            score += 3.0
        for t in q_tokens:
            if t in blob:
                score += 1.0
        if n.get("kind") == "preference" and score == 0:
            score = 0.2
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, n in scored[:top_k]:
        row = dict(n)
        row["_score"] = round(sc, 3)
        out.append(row)
    return out


def memories_to_chunks(notes: list[dict]) -> list[dict]:
    out = []
    for n in notes:
        if n.get("status", "active") != "active":
            continue
        text = (
            f"[{n.get('kind')}] {n.get('title')}\n"
            f"{n.get('content')}\n"
            f"code={n.get('code') or '-'} tags={','.join(n.get('tags') or [])}"
        )
        out.append(
            {
                "id": f"memory:{n.get('id')}",
                "text": text,
                "source": f"memory/{n.get('kind')}/{n.get('id')}",
                "meta": {"kind": n.get("kind"), "code": n.get("code"), "id": n.get("id")},
            }
        )
    return out


def format_memories_for_prompt(notes: list[dict]) -> str:
    if not notes:
        return "（暂无相关沉淀）"
    lines = []
    for n in notes:
        lines.append(
            f"- [{n.get('kind')}] {n.get('title')} "
            f"(code={n.get('code') or '-'}) {n.get('content')}"
        )
    return "\n".join(lines)
