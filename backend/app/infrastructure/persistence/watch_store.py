"""观察池标的。"""
from __future__ import annotations

from app.infrastructure.persistence import storage
from app.infrastructure.persistence.schema import ensure_schema


def load_watch_codes() -> list[str]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return list(storage.memory_blob()["watch_codes"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM watch_codes ORDER BY sort_no ASC, code ASC")
            rows = cur.fetchall() or []
        if rows:
            return [r["code"] for r in rows if r.get("code")]
        return []
    return []


def save_watch_codes(codes: list[str]) -> None:
    clean = [c for c in codes if isinstance(c, str) and c]
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["watch_codes"] = clean
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM watch_codes")
        for i, code in enumerate(clean):
            cur.execute(
                "INSERT INTO watch_codes (code, sort_no) VALUES (%s, %s)",
                (code[:16], i),
            )

