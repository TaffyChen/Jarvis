"""站内对话流水。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema


def load_conversations() -> list[dict[str, Any]]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return list(storage.memory_blob()["conversations"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, question, answer, sources_json, patch_json, memory_patch_json,
                       memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
                FROM conversations
                ORDER BY ts DESC, id DESC
                LIMIT 100
                """
            )
            rows = cur.fetchall() or []
        if rows:
            return [
                {
                    "id": r["id"],
                    "ts": codec.fmt_ts(r.get("ts")),
                    "question": r.get("question") or "",
                    "answer": r.get("answer") or "",
                    "sources": codec.loads(r.get("sources_json"), []),
                    "patch": codec.loads(r.get("patch_json"), None),
                    "memoryPatch": codec.loads(r.get("memory_patch_json"), None),
                    "memoriesUsed": codec.loads(r.get("memories_used_json"), []),
                    "toolTrace": codec.loads(r.get("tool_trace_json"), []),
                    "retrieveQueries": codec.loads(r.get("retrieve_queries_json"), []),
                    "orchestrator": r.get("orchestrator") or "graph",
                }
                for r in rows
            ]
        return []
    return []


def save_conversations(rows: list[dict[str, Any]] | None) -> None:
    rows = list(rows or [])[:100]
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["conversations"] = rows
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM conversations")
        for r in reversed(rows):
            cur.execute(
                """
                INSERT INTO conversations (
                  ts, question, answer, sources_json, patch_json, memory_patch_json,
                  memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    codec.parse_ts(r.get("ts")),
                    r.get("question") or "",
                    r.get("answer") or "",
                    codec.dumps(r.get("sources") or []),
                    codec.dumps(r.get("patch")) if r.get("patch") is not None else None,
                    codec.dumps(r.get("memoryPatch")) if r.get("memoryPatch") is not None else None,
                    codec.dumps(r.get("memoriesUsed") or []),
                    codec.dumps(r.get("toolTrace") or []),
                    codec.dumps(r.get("retrieveQueries") or []),
                    str(r.get("orchestrator") or "graph")[:32],
                ),
            )
