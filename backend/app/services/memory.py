"""对话沉淀：列表 / 检索 / HITL 写入。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.memory import memories_to_chunks, normalize_memory_item, rank_memories
from app.infrastructure.persistence.analyses_store import load_analyses, save_analyses
from app.infrastructure.persistence.memory_store import load_memories, save_memories


def list_memories(limit: int = 200) -> list[dict]:
    notes = load_memories()
    if not isinstance(notes, list):
        return []
    return notes[:limit]


def search_memories(query: str, top_k: int = 5) -> list[dict]:
    k = max(1, min(int(top_k or 5), 8))
    hits = rank_memories(list_memories(500), query or "", top_k=k)
    return [
        {
            "id": h.get("id"),
            "kind": h.get("kind"),
            "code": h.get("code"),
            "title": h.get("title"),
            "content": h.get("content"),
            "score": h.get("_score"),
        }
        for h in hits
    ]


def apply_memory_patch(patch: dict, *, source_question: str = "") -> dict[str, Any]:
    memories = patch.get("memories") if isinstance(patch, dict) else None
    if not isinstance(memories, list):
        return {"success": False, "applied": 0, "items": []}

    notes = list_memories(1000)
    analyses = load_analyses()
    applied: list[dict] = []

    for raw in memories:
        row = normalize_memory_item(raw, source_question=source_question)
        if not row:
            continue
        notes.insert(0, row)
        applied.append({"id": row["id"], "kind": row["kind"], "code": row.get("code")})
        code = row.get("code")
        if row["kind"] == "stock" and code:
            a = analyses.get(code) or {"code": code, "name": code}
            stamp = datetime.now(timezone.utc).date().isoformat()
            line = f"[{stamp}] {row['title']}: {row['content']}"
            prev = (a.get("notes") or "").strip()
            a["notes"] = f"{prev}\n{line}".strip() if prev else line
            a["reviewedAt"] = stamp
            analyses[code] = a

    save_memories(notes[:500])
    save_analyses(analyses)
    return {
        "success": True,
        "applied": len(applied),
        "items": applied,
        "summary": patch.get("summary") if isinstance(patch, dict) else None,
    }


def apply_memory_notes(patch: dict | None, *, source_question: str = "") -> dict[str, Any]:
    return apply_memory_patch(patch or {}, source_question=source_question)


def memories_as_chunks() -> list[dict]:
    return memories_to_chunks(list_memories(500))
