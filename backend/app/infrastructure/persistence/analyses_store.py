"""标的分析底稿。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema


def load_analyses() -> dict[str, Any]:
    if storage.memory_mode() and not storage.mysql_enabled():
        return dict(storage.memory_blob()["analyses"])
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT code, name, type, rating, rating_manual, reason, notes,
                       analysis_json, etf_json, reviewed_at, risk_ok, extra_json
                FROM analyses
                """
            )
            rows = cur.fetchall() or []
        if rows:
            out: dict[str, Any] = {}
            for r in rows:
                item = {
                    "code": r["code"],
                    "name": r.get("name") or "",
                    "type": r.get("type") or "stock",
                    "rating": r.get("rating") or None,
                    "ratingManual": r.get("rating_manual"),
                    "reason": r.get("reason") or "",
                    "notes": r.get("notes") or "",
                    "analysis": codec.loads(r.get("analysis_json"), []),
                    "etf": codec.loads(r.get("etf_json"), None),
                    "reviewedAt": str(r["reviewed_at"]) if r.get("reviewed_at") else None,
                    "riskOk": codec.risk_from_db(r.get("risk_ok")),
                }
                extra = codec.loads(r.get("extra_json"), {})
                if isinstance(extra, dict):
                    item.update(extra)
                out[r["code"]] = item
            return out
        return {}
    return {}


def save_analyses(data: dict[str, Any] | None) -> None:
    data = data if isinstance(data, dict) else {}
    if storage.memory_mode() and not storage.mysql_enabled():
        storage.memory_blob()["analyses"] = dict(data)
        return
    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    codes = [str(c)[:16] for c in data.keys()]
    known = {
        "code", "name", "type", "rating", "ratingManual", "reason", "notes",
        "analysis", "etf", "reviewedAt", "riskOk",
    }
    with conn.cursor() as cur:
        for code, raw in data.items():
            a = raw if isinstance(raw, dict) else {}
            extra = {k: v for k, v in a.items() if k not in known}
            cur.execute(
                """
                INSERT INTO analyses (
                  code, name, type, rating, rating_manual, reason, notes,
                  analysis_json, etf_json, reviewed_at, risk_ok, extra_json
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  name=VALUES(name), type=VALUES(type), rating=VALUES(rating),
                  rating_manual=VALUES(rating_manual), reason=VALUES(reason),
                  notes=VALUES(notes), analysis_json=VALUES(analysis_json),
                  etf_json=VALUES(etf_json), reviewed_at=VALUES(reviewed_at),
                  risk_ok=VALUES(risk_ok), extra_json=VALUES(extra_json)
                """,
                (
                    str(code)[:16],
                    str(a.get("name") or "")[:64],
                    str(a.get("type") or "stock")[:16],
                    str(a.get("rating") or "")[:32],
                    (str(a["ratingManual"])[:32] if a.get("ratingManual") not in (None, "") else None),
                    a.get("reason") or "",
                    a.get("notes") or "",
                    codec.dumps(a.get("analysis") or []),
                    codec.dumps(a.get("etf")) if a.get("etf") is not None else None,
                    codec.parse_date(a.get("reviewedAt")),
                    codec.risk_to_db(a.get("riskOk")),
                    codec.dumps(extra) if extra else None,
                ),
            )
        if codes:
            cur.execute(
                f"DELETE FROM analyses WHERE code NOT IN ({','.join(['%s'] * len(codes))})",
                codes,
            )
        else:
            cur.execute("DELETE FROM analyses")
