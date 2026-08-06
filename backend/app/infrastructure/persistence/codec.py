"""JSON / 日期编解码，供各业务 store 共用。"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any


def dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def loads(raw: Any, default: Any):
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def parse_date(raw: Any) -> date | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc).replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw or "").strip().replace("Z", "+00:00")
    if not text:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def fmt_ts(raw: Any) -> str:
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(raw or "")


def risk_to_db(val: Any) -> int | None:
    if val is True:
        return 1
    if val is False:
        return 0
    return None


def risk_from_db(val: Any):
    if val is None:
        return None
    return bool(int(val))
