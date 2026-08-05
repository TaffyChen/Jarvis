"""对话沉淀：结构化认知卡片（HITL 确认后落库）。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.infra.storage import read_json, write_json

_MEMORY_FILE = "memory_notes.json"
_KIND_OK = {"stock", "market", "preference", "error", "insight"}


def list_memories(limit: int = 200) -> list[dict]:
    notes = read_json(_MEMORY_FILE, [])
    if not isinstance(notes, list):
        return []
    return notes[:limit]


def search_memories(query: str, top_k: int = 5) -> list[dict]:
    """轻量关键词重叠检索，不依赖向量库。"""
    notes = [n for n in list_memories(500) if n.get("status", "active") == "active"]
    if not notes:
        return []
    q = (query or "").lower()
    q_tokens = set(re.findall(r"[\u4e00-\u9fff]{1,2}|[a-z0-9_]{2,}", q))
    scored: list[tuple[float, dict]] = []
    for n in notes:
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
        # 偏好类在无命中时也给一点保底曝光
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


def apply_memory_patch(patch: dict, *, source_question: str = "") -> dict[str, Any]:
    """确认后写入 memory_notes；stock 类可同步追加 analyses.notes。"""
    memories = patch.get("memories") if isinstance(patch, dict) else None
    if not isinstance(memories, list):
        return {"success": False, "applied": 0, "items": []}

    notes = list_memories(1000)
    analyses = read_json("analyses.json", {})
    applied: list[dict] = []

    for raw in memories:
        row = normalize_memory_item(raw, source_question=source_question)
        if not row:
            continue
        notes.insert(0, row)
        applied.append({"id": row["id"], "kind": row["kind"], "code": row.get("code")})

        # stock 认知同步到 analyses.notes（追加，不覆盖原有）
        code = row.get("code")
        if row["kind"] == "stock" and code:
            a = analyses.get(code) or {"code": code, "name": code}
            stamp = datetime.now(timezone.utc).date().isoformat()
            line = f"[{stamp}] {row['title']}: {row['content']}"
            prev = (a.get("notes") or "").strip()
            a["notes"] = f"{prev}\n{line}".strip() if prev else line
            a["reviewedAt"] = stamp
            analyses[code] = a

    write_json(_MEMORY_FILE, notes[:500])
    write_json("analyses.json", analyses)
    return {
        "success": True,
        "applied": len(applied),
        "items": applied,
        "summary": patch.get("summary") if isinstance(patch, dict) else None,
    }


def memories_as_chunks() -> list[dict]:
    """供 reindex 使用的纯 dict 片段。"""
    out = []
    for n in list_memories(500):
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
