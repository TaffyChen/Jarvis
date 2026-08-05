"""对话沉淀卡片。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema


def load_memories() -> list[dict[str, Any]]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return list(storage.memory_blob()["memories"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, kind, code, title, content, tags_json, expires_at,
                       source_question, status
                FROM memory_notes
                ORDER BY ts DESC, id DESC
                """
            )
            rows = cur.fetchall() or []
        if rows:
            out = []
            for r in rows:
                out.append(
                    {
                        "id": r["id"],
                        "ts": codec.fmt_ts(r.get("ts")),
                        "kind": r.get("kind") or "insight",
                        "code": r.get("code") or None,
                        "title": r.get("title") or "",
                        "content": r.get("content") or "",
                        "tags": codec.loads(r.get("tags_json"), []),
                        "expiresAt": r.get("expires_at"),
                        "sourceQuestion": r.get("source_question") or "",
                        "status": r.get("status") or "active",
                    }
                )
            return out
        return []
    return []


def save_memories(notes: list[dict[str, Any]] | None) -> None:
    notes = list(notes or [])[:500]
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["memories"] = notes
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    ids = [str(n.get("id") or "") for n in notes if n.get("id")]
    with conn.cursor() as cur:
        for n in notes:
            if not n.get("id"):
                continue
            cur.execute(
                """
                INSERT INTO memory_notes (
                  id, ts, kind, code, title, content, tags_json, expires_at, source_question, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  ts=VALUES(ts), kind=VALUES(kind), code=VALUES(code), title=VALUES(title),
                  content=VALUES(content), tags_json=VALUES(tags_json), expires_at=VALUES(expires_at),
                  source_question=VALUES(source_question), status=VALUES(status)
                """,
                (
                    str(n["id"])[:64],
                    codec.parse_ts(n.get("ts")),
                    str(n.get("kind") or "insight")[:32],
                    str(n.get("code") or "")[:16],
                    str(n.get("title") or "")[:255],
                    n.get("content") or "",
                    codec.dumps(n.get("tags") or []),
                    (str(n["expiresAt"])[:64] if n.get("expiresAt") else None),
                    str(n.get("sourceQuestion") or "")[:255],
                    str(n.get("status") or "active")[:16],
                ),
            )
        if ids:
            cur.execute(
                f"DELETE FROM memory_notes WHERE id NOT IN ({','.join(['%s'] * len(ids))})",
                ids,
            )
        else:
            cur.execute("DELETE FROM memory_notes")
