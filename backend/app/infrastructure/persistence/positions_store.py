"""持仓表。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema


def load_positions() -> dict[str, Any]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return dict(storage.memory_blob()["positions"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code, name, buy_price, shares, buy_date, extra_json FROM positions"
            )
            rows = cur.fetchall() or []
        if rows:
            out: dict[str, Any] = {}
            for r in rows:
                item = {
                    "buyPrice": float(r["buy_price"]),
                    "shares": float(r["shares"]),
                }
                if r.get("name"):
                    item["name"] = r["name"]
                if r.get("buy_date"):
                    item["date"] = str(r["buy_date"])
                extra = codec.loads(r.get("extra_json"), {})
                if isinstance(extra, dict):
                    item.update(extra)
                out[r["code"]] = item
            return out
        return {}
    return {}


def save_positions(data: dict[str, Any] | None) -> None:
    data = data if isinstance(data, dict) else {}
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["positions"] = dict(data)
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    codes = [str(c)[:16] for c in data.keys()]
    with conn.cursor() as cur:
        for code, raw in data.items():
            p = raw if isinstance(raw, dict) else {}
            known = {"buyPrice", "shares", "date", "name"}
            extra = {k: v for k, v in p.items() if k not in known}
            cur.execute(
                """
                INSERT INTO positions (code, name, buy_price, shares, buy_date, extra_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  name=VALUES(name), buy_price=VALUES(buy_price), shares=VALUES(shares),
                  buy_date=VALUES(buy_date), extra_json=VALUES(extra_json)
                """,
                (
                    str(code)[:16],
                    str(p.get("name") or "")[:64],
                    float(p.get("buyPrice") or 0),
                    float(p.get("shares") or 0),
                    codec.parse_date(p.get("date")),
                    codec.dumps(extra) if extra else None,
                ),
            )
        if codes:
            cur.execute(
                f"DELETE FROM positions WHERE code NOT IN ({','.join(['%s'] * len(codes))})",
                codes,
            )
        else:
            cur.execute("DELETE FROM positions")
