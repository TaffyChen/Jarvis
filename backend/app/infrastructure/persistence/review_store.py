"""盘面简报：按交易日多版本追加，可标定稿。"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from app.infrastructure.persistence import codec, storage
from app.infrastructure.persistence.schema import ensure_schema

_HEADLINE_RE = re.compile(r"\*\*一句话定性[：:]\*\*\s*(.+)")


def list_days(limit: int = 60) -> list[dict[str, Any]]:
    """左侧按日聚合。"""
    limit = max(1, min(int(limit or 60), 120))
    if storage.memory_mode() and not storage.mysql_enabled():
        by_day: dict[str, list[dict[str, Any]]] = {}
        for row in storage.memory_blob().get("market_briefs") or []:
            d = row.get("date") or ""
            by_day.setdefault(d, []).append(row)
        days = sorted(by_day.keys(), reverse=True)[:limit]
        out = []
        for d in days:
            vers = sorted(by_day[d], key=lambda r: r.get("createdAt") or "", reverse=True)
            latest = vers[0]
            out.append(
                {
                    "date": d,
                    "versionCount": len(vers),
                    "headline": latest.get("headline") or "",
                    "hasFinal": any(bool(v.get("isFinal")) for v in vers),
                    "latestAt": latest.get("createdAt"),
                    "latestId": latest.get("id"),
                }
            )
        return out

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT brief_date,
                   COUNT(*) AS version_count,
                   MAX(CASE WHEN is_final = 1 THEN 1 ELSE 0 END) AS has_final,
                   MAX(created_at) AS latest_at
            FROM market_briefs
            GROUP BY brief_date
            ORDER BY brief_date DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall() or []
    out = []
    for r in rows:
        d = r.get("brief_date")
        day = d.isoformat() if isinstance(d, date) else str(d)[:10]
        latest = get_latest_for_day(day)
        out.append(
            {
                "date": day,
                "versionCount": int(r.get("version_count") or 0),
                "headline": (latest or {}).get("headline") or "",
                "hasFinal": bool(int(r.get("has_final") or 0)),
                "latestAt": codec.fmt_ts(r.get("latest_at")),
                "latestId": (latest or {}).get("id"),
            }
        )
    return out


def list_versions_for_day(brief_date: str | date) -> list[dict[str, Any]]:
    day = _as_date(brief_date)
    if not day:
        return []
    key = day.isoformat()
    if storage.memory_mode() and not storage.mysql_enabled():
        rows = [r for r in (storage.memory_blob().get("market_briefs") or []) if r.get("date") == key]
        rows.sort(key=lambda r: r.get("createdAt") or "", reverse=True)
        return [_summary(r) for r in rows]

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, brief_date, headline, model, is_final, created_at, updated_at,
                   JSON_LENGTH(comments_json) AS comment_count,
                   CHAR_LENGTH(report_md) AS report_len
            FROM market_briefs
            WHERE brief_date = %s
            ORDER BY created_at DESC, id DESC
            """,
            (day,),
        )
        rows = cur.fetchall() or []
    return [
        {
            "id": int(r["id"]),
            "date": key,
            "headline": r.get("headline") or "",
            "model": r.get("model") or "",
            "isFinal": bool(int(r.get("is_final") or 0)),
            "commentCount": int(r.get("comment_count") or 0),
            "hasReport": int(r.get("report_len") or 0) > 0,
            "createdAt": codec.fmt_ts(r.get("created_at")),
            "updatedAt": codec.fmt_ts(r.get("updated_at")),
        }
        for r in rows
    ]


def get_version(version_id: int) -> dict[str, Any] | None:
    vid = int(version_id)
    if storage.memory_mode() and not storage.mysql_enabled():
        for row in storage.memory_blob().get("market_briefs") or []:
            if int(row.get("id") or 0) == vid:
                return dict(row)
        return None

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, brief_date, snapshot_json, report_md, comments_json, headline, model,
                   is_final, created_at, updated_at
            FROM market_briefs WHERE id = %s
            """,
            (vid,),
        )
        r = cur.fetchone()
    if not r:
        return None
    return _row_to_version(r)


def get_latest_for_day(brief_date: str | date) -> dict[str, Any] | None:
    vers = list_versions_for_day(brief_date)
    if not vers:
        return None
    return get_version(int(vers[0]["id"]))


def get_day_bundle(brief_date: str | date) -> dict[str, Any] | None:
    day = _as_date(brief_date)
    if not day:
        return None
    versions = list_versions_for_day(day)
    if not versions:
        return None
    return {
        "date": day.isoformat(),
        "versions": versions,
        "finalId": next((v["id"] for v in versions if v.get("isFinal")), None),
    }


def create_version(
    *,
    brief_date: str | date,
    snapshot: dict[str, Any],
    report_md: str,
    model: str = "",
    comments: list[dict[str, Any]] | None = None,
    is_final: bool = False,
) -> dict[str, Any]:
    day = _as_date(brief_date) or date.today()
    key = day.isoformat()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    headline = _extract_headline(report_md)
    row = {
        "date": key,
        "snapshot": snapshot or {},
        "reportMd": report_md or "",
        "comments": list(comments or []),
        "headline": headline,
        "model": (model or "")[:64],
        "isFinal": bool(is_final),
        "createdAt": codec.fmt_ts(now),
        "updatedAt": codec.fmt_ts(now),
    }

    if storage.memory_mode() and not storage.mysql_enabled():
        blob = storage.memory_blob().setdefault("market_briefs", [])
        vid = max((int(x.get("id") or 0) for x in blob), default=0) + 1
        row["id"] = vid
        if is_final:
            for x in blob:
                if x.get("date") == key:
                    x["isFinal"] = False
        blob.append(row)
        return dict(row)

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        if is_final:
            cur.execute(
                "UPDATE market_briefs SET is_final = 0, updated_at = %s WHERE brief_date = %s",
                (now, day),
            )
        cur.execute(
            """
            INSERT INTO market_briefs (
              brief_date, snapshot_json, report_md, comments_json, headline, model,
              is_final, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                day,
                codec.dumps(row["snapshot"]),
                row["reportMd"],
                codec.dumps(row["comments"]),
                row["headline"],
                row["model"],
                1 if is_final else 0,
                now,
                now,
            ),
        )
        vid = int(cur.lastrowid)
    return get_version(vid) or {**row, "id": vid}


def add_comment(version_id: int, text: str) -> dict[str, Any] | None:
    note = " ".join(str(text or "").split()).strip()
    if not note:
        raise ValueError("评论不能为空")
    row = get_version(version_id)
    if not row:
        return None
    comments = list(row.get("comments") or [])
    comments.append(
        {
            "ts": codec.fmt_ts(datetime.now(timezone.utc).replace(tzinfo=None)),
            "text": note[:2000],
        }
    )
    row["comments"] = comments
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row["updatedAt"] = codec.fmt_ts(now)

    if storage.memory_mode() and not storage.mysql_enabled():
        for i, x in enumerate(storage.memory_blob().get("market_briefs") or []):
            if int(x.get("id") or 0) == int(version_id):
                storage.memory_blob()["market_briefs"][i] = row
                return dict(row)
        return None

    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE market_briefs
            SET comments_json = %s, updated_at = %s
            WHERE id = %s
            """,
            (codec.dumps(comments), now, int(version_id)),
        )
    return get_version(version_id)


def mark_final(version_id: int) -> dict[str, Any] | None:
    row = get_version(version_id)
    if not row:
        return None
    day = _as_date(row.get("date"))
    if not day:
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if storage.memory_mode() and not storage.mysql_enabled():
        for x in storage.memory_blob().get("market_briefs") or []:
            if x.get("date") == day.isoformat():
                x["isFinal"] = int(x.get("id") or 0) == int(version_id)
                if x["isFinal"]:
                    x["updatedAt"] = codec.fmt_ts(now)
        return get_version(version_id)

    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE market_briefs SET is_final = 0, updated_at = %s WHERE brief_date = %s",
            (now, day),
        )
        cur.execute(
            "UPDATE market_briefs SET is_final = 1, updated_at = %s WHERE id = %s",
            (now, int(version_id)),
        )
    return get_version(version_id)


def recent_for_context(limit: int = 5, exclude_id: int | None = None) -> list[dict[str, Any]]:
    """再生成上下文：近几版 headline + 批注。"""
    items: list[dict[str, Any]] = []
    if storage.memory_mode() and not storage.mysql_enabled():
        rows = sorted(
            storage.memory_blob().get("market_briefs") or [],
            key=lambda r: r.get("createdAt") or "",
            reverse=True,
        )
        for r in rows:
            if exclude_id is not None and int(r.get("id") or 0) == int(exclude_id):
                continue
            items.append(
                {
                    "id": r.get("id"),
                    "date": r.get("date"),
                    "headline": r.get("headline") or "",
                    "isFinal": bool(r.get("isFinal")),
                    "comments": r.get("comments") or [],
                    "createdAt": r.get("createdAt"),
                }
            )
            if len(items) >= limit:
                break
        return items

    if not storage.mysql_enabled():
        storage.require_mysql()
    ensure_schema()
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, brief_date, headline, comments_json, is_final, created_at
            FROM market_briefs
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit + 3,),
        )
        rows = cur.fetchall() or []
    for r in rows:
        vid = int(r["id"])
        if exclude_id is not None and vid == int(exclude_id):
            continue
        d = r.get("brief_date")
        items.append(
            {
                "id": vid,
                "date": d.isoformat() if isinstance(d, date) else str(d)[:10],
                "headline": r.get("headline") or "",
                "isFinal": bool(int(r.get("is_final") or 0)),
                "comments": codec.loads(r.get("comments_json"), []),
                "createdAt": codec.fmt_ts(r.get("created_at")),
            }
        )
        if len(items) >= limit:
            break
    return items


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "date": row.get("date"),
        "headline": row.get("headline") or "",
        "model": row.get("model") or "",
        "isFinal": bool(row.get("isFinal")),
        "commentCount": len(row.get("comments") or []),
        "hasReport": bool(row.get("reportMd")),
        "createdAt": row.get("createdAt"),
        "updatedAt": row.get("updatedAt"),
    }


def _row_to_version(r: dict[str, Any]) -> dict[str, Any]:
    d = r.get("brief_date")
    return {
        "id": int(r["id"]),
        "date": d.isoformat() if isinstance(d, date) else str(d)[:10],
        "snapshot": codec.loads(r.get("snapshot_json"), {}),
        "reportMd": r.get("report_md") or "",
        "comments": codec.loads(r.get("comments_json"), []),
        "headline": r.get("headline") or "",
        "model": r.get("model") or "",
        "isFinal": bool(int(r.get("is_final") or 0)),
        "createdAt": codec.fmt_ts(r.get("created_at")),
        "updatedAt": codec.fmt_ts(r.get("updated_at")),
    }


def _as_date(raw: str | date | None) -> date | None:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    return codec.parse_date(raw)


def _extract_headline(md: str) -> str:
    text = md or ""
    m = _HEADLINE_RE.search(text)
    if m:
        return m.group(1).strip()[:240]
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and "简报" not in line[:6] and "复盘" not in line[:6]:
            return line[:240]
    return ""
