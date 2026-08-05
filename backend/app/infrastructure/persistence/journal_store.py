"""纪律日记：MySQL 一行一条。pytest 无库时走内存；遗留 journal.json 仅启动迁移一次。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.domain.codes import looks_like_code, normalize_code
from app.infrastructure.persistence import storage

_MAX_KEEP = 500
_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS journal_entries (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id BIGINT DEFAULT NULL COMMENT '用户ID，预留多用户；单机历史可空',
  ts DATETIME(3) NOT NULL COMMENT '日记发生时间（UTC）',
  code VARCHAR(16) NOT NULL DEFAULT '' COMMENT '标的代码，如 sz000636；组合级可用 ALL',
  name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '标的或来源名称',
  level VARCHAR(16) NOT NULL DEFAULT '' COMMENT '级别：danger / warning / info',
  msg VARCHAR(512) NOT NULL DEFAULT '' COMMENT '告警或事件原文',
  action VARCHAR(128) NOT NULL DEFAULT '' COMMENT '建议或已执行动作',
  note TEXT NOT NULL COMMENT '用户备注',
  lamps TINYINT DEFAULT NULL COMMENT '记录时五灯红灯数，可空',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (id),
  KEY idx_journal_ts (ts),
  KEY idx_journal_code (code),
  KEY idx_journal_user_ts (user_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='纪律日记：持仓预警与策略留痕，一行一条'
"""


def ensure_schema() -> None:
    if not storage.mysql_enabled():
        return
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(_TABLE_SQL)


def list_journal_entries(
    limit: int | None = None,
    *,
    q: str | None = None,
    level: str | None = None,
    code: str | None = None,
) -> list[dict[str, Any]]:
    query = (q or "").strip()
    lvl = _normalize_level(level)
    code_filter = normalize_code(code) if looks_like_code(code) else (code or "").strip().lower()
    if storage.memory_mode() and not storage.mysql_enabled():
        rows = [
            row
            for row in storage.memory_blob()["journal"]
            if _entry_matches(row, query=query, level=lvl, code=code_filter)
        ]
        if limit is not None:
            return rows[: max(1, int(limit))]
        return rows
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        sql = """
            SELECT id, user_id, ts, code, name, level, msg, action, note, lamps, created_at
            FROM journal_entries
            WHERE 1=1
        """
        params: list[Any] = []
        if query:
            like = f"%{_escape_like(query)}%"
            sql += """
              AND (
                code LIKE %s ESCAPE '\\\\'
                OR REPLACE(REPLACE(LOWER(code), 'sh', ''), 'sz', '') LIKE %s ESCAPE '\\\\'
                OR name LIKE %s ESCAPE '\\\\'
                OR msg LIKE %s ESCAPE '\\\\'
                OR action LIKE %s ESCAPE '\\\\'
                OR note LIKE %s ESCAPE '\\\\'
              )
            """
            params.extend([like, like.lower(), like, like, like, like])
        if lvl:
            sql += " AND LOWER(level) = %s"
            params.append(lvl)
        if code_filter:
            sql += " AND (code = %s OR LOWER(code) = %s)"
            params.extend([code_filter, code_filter])
        sql += " ORDER BY ts DESC, id DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(max(1, int(limit)))
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []
        return [_row_to_entry(r) for r in rows]
    return []


def add_journal_entry(entry: dict[str, Any] | None) -> dict[str, Any]:
    item = _normalize(entry or {})
    if storage.memory_mode() and not storage.mysql_enabled():
        rows = storage.memory_blob()["journal"]
        row = {k: v for k, v in item.items() if k != "user_id"}
        rows.insert(0, row)
        del rows[_MAX_KEEP:]
        return row
    if not storage.mysql_enabled():
        storage.require_mysql()
    if storage.mysql_enabled():
        ensure_schema()
        conn = storage.mysql_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO journal_entries (user_id, ts, code, name, level, msg, action, note, lamps)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item.get("user_id"),
                    _parse_ts(item.get("ts")),
                    item["code"],
                    item["name"],
                    item["level"],
                    item["msg"],
                    item["action"],
                    item["note"],
                    item.get("lamps"),
                ),
            )
            new_id = cur.lastrowid
            cur.execute(
                """
                DELETE FROM journal_entries
                WHERE id NOT IN (
                  SELECT id FROM (
                    SELECT id FROM journal_entries ORDER BY ts DESC, id DESC LIMIT %s
                  ) keep_rows
                )
                """,
                (_MAX_KEEP,),
            )
        item["id"] = new_id
        return item
    return item


def migrate_legacy() -> dict[str, Any]:
    """把 kv_docs / 本地 journal.json 迁进表，然后删掉日记 JSON 源。"""
    if not storage.mysql_enabled():
        return {"migrated": 0, "skipped": "mysql_disabled"}
    ensure_schema()
    blob_rows: list[dict[str, Any]] = []
    try:
        payload = storage._mysql_read("journal.json")  # noqa: SLF001
        if isinstance(payload, list):
            blob_rows.extend(payload)
    except Exception:
        pass
    file_rows = storage._file_read("journal.json", [])  # noqa: SLF001
    if isinstance(file_rows, list):
        blob_rows.extend(file_rows)

    existing = {
        (_parse_ts(r.get("ts")).isoformat(), r.get("code") or "", r.get("msg") or "", r.get("note") or "")
        for r in list_journal_entries()
    }
    inserted = 0
    for raw in blob_rows:
        if not isinstance(raw, dict):
            continue
        item = _normalize(raw)
        key = (_parse_ts(item.get("ts")).isoformat(), item["code"], item["msg"], item["note"])
        if key in existing:
            continue
        add_journal_entry(item)
        existing.add(key)
        inserted += 1

    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM kv_docs WHERE doc_name = %s", ("journal.json",))
    path = settings.data_dir / "journal.json"
    if path.exists():
        path.unlink()
    return {"migrated": inserted, "clearedJson": True}


def _normalize(entry: dict[str, Any]) -> dict[str, Any]:
    lamps = entry.get("lamps")
    try:
        lamps_val = int(lamps) if lamps is not None and str(lamps) != "" else None
    except (TypeError, ValueError):
        lamps_val = None
    user_id = entry.get("user_id")
    try:
        user_id = int(user_id) if user_id is not None and str(user_id) != "" else None
    except (TypeError, ValueError):
        user_id = None
    ts = entry.get("ts") or datetime.now(timezone.utc).isoformat()
    return {
        "user_id": user_id,
        "ts": ts,
        "code": str(entry.get("code") or "")[:16],
        "name": str(entry.get("name") or "")[:64],
        "level": str(entry.get("level") or "")[:16],
        "msg": str(entry.get("msg") or "")[:512],
        "action": str(entry.get("action") or "")[:128],
        "note": str(entry.get("note") or ""),
        "lamps": lamps_val,
    }


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    text = str(raw or "").strip()
    if not text:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _normalize_level(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    if text in ("warn", "warning"):
        return "warning"
    if text in ("danger", "info", "warning"):
        return text
    return ""


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _entry_matches(row: dict[str, Any], *, query: str, level: str, code: str) -> bool:
    row_level = _normalize_level(row.get("level"))
    if level and row_level != level:
        return False
    row_code = str(row.get("code") or "").strip().lower()
    if code and row_code != code and normalize_code(row_code) != code:
        return False
    if not query:
        return True
    needle = query.lower()
    digits = "".join(ch for ch in needle if ch.isdigit())
    bare_code = row_code[2:] if row_code.startswith(("sh", "sz")) else row_code
    hay = " ".join(
        [
            row_code,
            bare_code,
            str(row.get("name") or ""),
            str(row.get("msg") or ""),
            str(row.get("action") or ""),
            str(row.get("note") or ""),
            str(row.get("level") or ""),
        ]
    ).lower()
    if needle in hay:
        return True
    return bool(digits) and digits in hay


def _row_to_entry(row: dict[str, Any]) -> dict[str, Any]:
    ts = row.get("ts")
    if isinstance(ts, datetime):
        ts_out = ts.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        ts_out = str(ts or "")
    return {
        "id": row.get("id"),
        "ts": ts_out,
        "code": row.get("code") or "",
        "name": row.get("name") or "",
        "level": row.get("level") or "",
        "msg": row.get("msg") or "",
        "action": row.get("action") or "",
        "note": row.get("note") or "",
        "lamps": row.get("lamps"),
    }
