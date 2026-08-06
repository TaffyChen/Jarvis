"""站内对话：会话列表 + 轮次流水。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema

_MAX_TURNS = 300
_MAX_SESSIONS = 80


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(title: str = "") -> dict[str, Any]:
    title = _clip_title(title)
    now = _now()
    if storage.memory_mode() and not storage.mysql_enabled():
        blob = storage.memory_blob()
        sessions = blob.setdefault("chat_sessions", [])
        sid = (max((int(s.get("id") or 0) for s in sessions), default=0) + 1)
        row = {
            "id": sid,
            "title": title or "新对话",
            "createdAt": codec.fmt_ts(now),
            "updatedAt": codec.fmt_ts(now),
        }
        sessions.insert(0, row)
        del sessions[_MAX_SESSIONS:]
        return row
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_sessions (title, created_at, updated_at)
            VALUES (%s, %s, %s)
            """,
            (title or "新对话", now, now),
        )
        sid = int(cur.lastrowid)
    return {"id": sid, "title": title or "新对话", "createdAt": codec.fmt_ts(now), "updatedAt": codec.fmt_ts(now)}


def list_sessions(limit: int = 40) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 40), _MAX_SESSIONS))
    _backfill_orphan_sessions()
    if storage.memory_mode() and not storage.mysql_enabled():
        sessions = list(storage.memory_blob().get("chat_sessions") or [])
        sessions.sort(key=lambda s: s.get("updatedAt") or "", reverse=True)
        out = []
        for s in sessions[:limit]:
            turns = [t for t in storage.memory_blob().get("conversations") or [] if t.get("sessionId") == s.get("id")]
            preview = (turns[0].get("question") if turns else "") or ""
            out.append({**s, "preview": _clip_title(preview, 48), "turnCount": len(turns)})
        return out
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   (SELECT c.question FROM conversations c
                    WHERE c.session_id = s.id ORDER BY c.ts DESC, c.id DESC LIMIT 1) AS preview,
                   (SELECT COUNT(*) FROM conversations c WHERE c.session_id = s.id) AS turn_count
            FROM chat_sessions s
            ORDER BY s.updated_at DESC, s.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall() or []
    return [
        {
            "id": r["id"],
            "title": r.get("title") or "新对话",
            "createdAt": codec.fmt_ts(r.get("created_at")),
            "updatedAt": codec.fmt_ts(r.get("updated_at")),
            "preview": _clip_title(r.get("preview") or "", 48),
            "turnCount": int(r.get("turn_count") or 0),
        }
        for r in rows
    ]


def get_session(session_id: int) -> dict[str, Any] | None:
    sid = int(session_id)
    if storage.memory_mode() and not storage.mysql_enabled():
        sessions = storage.memory_blob().get("chat_sessions") or []
        meta = next((s for s in sessions if int(s.get("id") or 0) == sid), None)
        if not meta:
            return None
        turns = [
            _normalize_turn(t)
            for t in storage.memory_blob().get("conversations") or []
            if int(t.get("sessionId") or 0) == sid
        ]
        turns.sort(key=lambda t: (t.get("ts") or "", t.get("id") or 0))
        return {"session": meta, "turns": turns, "messages": _turns_to_messages(turns)}
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = %s",
            (sid,),
        )
        s = cur.fetchone()
        if not s:
            return None
        cur.execute(
            """
            SELECT id, session_id, ts, question, answer, sources_json, patch_json, memory_patch_json,
                   memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
            FROM conversations
            WHERE session_id = %s
            ORDER BY ts ASC, id ASC
            """,
            (sid,),
        )
        rows = cur.fetchall() or []
    turns = [_row_to_turn(r) for r in rows]
    session = {
        "id": s["id"],
        "title": s.get("title") or "新对话",
        "createdAt": codec.fmt_ts(s.get("created_at")),
        "updatedAt": codec.fmt_ts(s.get("updated_at")),
    }
    return {"session": session, "turns": turns, "messages": _turns_to_messages(turns)}


def append_turn(row: dict[str, Any], session_id: int | None = None) -> dict[str, Any]:
    """追加一轮问答；无 session 时自动建会话。"""
    sid = int(session_id) if session_id else None
    question = (row.get("question") or "").strip()
    if not sid:
        created = create_session(_clip_title(question))
        sid = int(created["id"])
    else:
        _touch_session(sid, title_if_empty=_clip_title(question))

    item = {
        "sessionId": sid,
        "ts": row.get("ts") or codec.fmt_ts(_now()),
        "question": question,
        "answer": row.get("answer") or "",
        "sources": row.get("sources") or [],
        "patch": row.get("patch"),
        "memoryPatch": row.get("memoryPatch"),
        "memoriesUsed": row.get("memoriesUsed") or [],
        "toolTrace": row.get("toolTrace") or [],
        "retrieveQueries": row.get("retrieveQueries") or [],
        "orchestrator": row.get("orchestrator") or "graph",
    }

    if storage.memory_mode() and not storage.mysql_enabled():
        turns = storage.memory_blob().setdefault("conversations", [])
        item["id"] = max((int(t.get("id") or 0) for t in turns), default=0) + 1
        turns.insert(0, item)
        del turns[_MAX_TURNS:]
        return {"sessionId": sid, "turn": item}

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO conversations (
              session_id, ts, question, answer, sources_json, patch_json, memory_patch_json,
              memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                sid,
                codec.parse_ts(item["ts"]),
                item["question"],
                item["answer"],
                codec.dumps(item["sources"]),
                codec.dumps(item["patch"]) if item.get("patch") is not None else None,
                codec.dumps(item["memoryPatch"]) if item.get("memoryPatch") is not None else None,
                codec.dumps(item["memoriesUsed"]),
                codec.dumps(item["toolTrace"]),
                codec.dumps(item["retrieveQueries"]),
                str(item["orchestrator"])[:32],
            ),
        )
        item["id"] = int(cur.lastrowid)
        cur.execute("SELECT COUNT(*) AS c FROM conversations")
        total = int((cur.fetchone() or {}).get("c") or 0)
        excess = total - _MAX_TURNS
        if excess > 0:
            cur.execute(
                "SELECT id FROM conversations ORDER BY ts ASC, id ASC LIMIT %s",
                (excess,),
            )
            old_ids = [int(r["id"]) for r in (cur.fetchall() or [])]
            if old_ids:
                cur.execute(
                    f"DELETE FROM conversations WHERE id IN ({','.join(['%s'] * len(old_ids))})",
                    tuple(old_ids),
                )
    return {"sessionId": sid, "turn": item}


# —— 兼容旧 API ——

def load_conversations() -> list[dict[str, Any]]:
    if storage.memory_mode() and not storage.mysql_enabled():
        rows = list(storage.memory_blob().get("conversations") or [])
        return [_normalize_turn(r) for r in rows]
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, session_id, ts, question, answer, sources_json, patch_json, memory_patch_json,
                   memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
            FROM conversations
            ORDER BY ts DESC, id DESC
            LIMIT %s
            """,
            (_MAX_TURNS,),
        )
        rows = cur.fetchall() or []
    return [_row_to_turn(r) for r in rows]


def save_conversations(rows: list[dict[str, Any]] | None) -> None:
    """迁移/测试用整表覆盖写入。"""
    rows = list(rows or [])[:_MAX_TURNS]
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["conversations"] = [_normalize_turn(r) for r in rows]
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
                  session_id, ts, question, answer, sources_json, patch_json, memory_patch_json,
                  memories_used_json, tool_trace_json, retrieve_queries_json, orchestrator
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    r.get("sessionId") or r.get("session_id"),
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


def _touch_session(session_id: int, title_if_empty: str = "") -> None:
    now = _now()
    if storage.memory_mode() and not storage.mysql_enabled():
        for s in storage.memory_blob().get("chat_sessions") or []:
            if int(s.get("id") or 0) == int(session_id):
                s["updatedAt"] = codec.fmt_ts(now)
                if title_if_empty and (not s.get("title") or s.get("title") == "新对话"):
                    s["title"] = title_if_empty
                break
        return
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        if title_if_empty:
            cur.execute(
                """
                UPDATE chat_sessions
                SET updated_at = %s,
                    title = CASE WHEN title = '' OR title = '新对话' THEN %s ELSE title END
                WHERE id = %s
                """,
                (now, title_if_empty, session_id),
            )
        else:
            cur.execute("UPDATE chat_sessions SET updated_at = %s WHERE id = %s", (now, session_id))


def _backfill_orphan_sessions() -> None:
    """把无 session_id 的旧轮次各建一个会话，便于左侧点选。"""
    if storage.memory_mode() and not storage.mysql_enabled():
        blob = storage.memory_blob()
        sessions = blob.setdefault("chat_sessions", [])
        turns = blob.setdefault("conversations", [])
        for t in turns:
            if t.get("sessionId"):
                continue
            created = create_session(_clip_title(t.get("question") or "历史对话"))
            t["sessionId"] = created["id"]
        return
    if not storage.mysql_enabled():
        return
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, question, ts FROM conversations
            WHERE session_id IS NULL
            ORDER BY ts ASC, id ASC
            LIMIT 100
            """
        )
        orphans = cur.fetchall() or []
        for o in orphans:
            title = _clip_title(o.get("question") or "历史对话")
            ts = o.get("ts") or _now()
            cur.execute(
                "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (%s,%s,%s)",
                (title, ts, ts),
            )
            sid = int(cur.lastrowid)
            cur.execute("UPDATE conversations SET session_id = %s WHERE id = %s", (sid, o["id"]))


def _clip_title(text: str, n: int = 28) -> str:
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _row_to_turn(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "sessionId": r.get("session_id"),
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


def _normalize_turn(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "sessionId": r.get("sessionId") or r.get("session_id"),
        "ts": r.get("ts") or "",
        "question": r.get("question") or "",
        "answer": r.get("answer") or "",
        "sources": r.get("sources") or [],
        "patch": r.get("patch"),
        "memoryPatch": r.get("memoryPatch"),
        "memoriesUsed": r.get("memoriesUsed") or [],
        "toolTrace": r.get("toolTrace") or [],
        "retrieveQueries": r.get("retrieveQueries") or [],
        "orchestrator": r.get("orchestrator") or "graph",
    }


def _turns_to_messages(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for t in turns:
        q = (t.get("question") or "").strip()
        a = (t.get("answer") or "").strip()
        if q:
            messages.append({"role": "user", "content": q})
        if a:
            messages.append(
                {
                    "role": "assistant",
                    "content": a,
                    "sources": t.get("sources") or [],
                    "patch": None,
                    "memoryPatch": None,
                    "memoriesUsed": t.get("memoriesUsed") or [],
                    "toolTrace": t.get("toolTrace") or [],
                    "retrieveQueries": t.get("retrieveQueries") or [],
                    "orchestrator": t.get("orchestrator"),
                    "sourceQuestion": q,
                    "fromHistory": True,
                }
            )
    return messages
