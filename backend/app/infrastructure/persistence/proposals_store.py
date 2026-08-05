"""策略/规则提案记录。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema


def load_proposals() -> list[dict[str, Any]]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return list(storage.memory_blob()["proposals"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ts, summary, payload_json, status FROM strategy_proposals ORDER BY ts DESC, id DESC"
            )
            rows = cur.fetchall() or []
        if rows:
            return [
                {
                    "id": r["id"],
                    "ts": codec.fmt_ts(r.get("ts")),
                    "summary": r.get("summary"),
                    "payload": codec.loads(r.get("payload_json"), {}),
                    "status": r.get("status") or "accepted",
                }
                for r in rows
            ]
        return []
    return []


def save_proposals(rows: list[dict[str, Any]] | None) -> None:
    rows = list(rows or [])[:200]
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["proposals"] = rows
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM strategy_proposals")
        for r in reversed(rows):
            cur.execute(
                """
                INSERT INTO strategy_proposals (ts, summary, payload_json, status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    codec.parse_ts(r.get("ts")),
                    r.get("summary"),
                    codec.dumps(r.get("payload") or {}),
                    str(r.get("status") or "accepted")[:32],
                ),
            )
