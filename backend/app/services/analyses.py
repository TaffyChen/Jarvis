"""标的分析底稿。"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.infrastructure.persistence.analyses_store import load_analyses, save_analyses


def list_analyses() -> dict[str, Any]:
    return {
        "analyses": load_analyses() or {},
        "staleDays": settings.analysis_stale_days,
    }


def get_analysis(code: str) -> dict[str, Any]:
    from app.domain.codes import normalize_code

    c = normalize_code(code) or (code or "").strip().lower()
    a = (load_analyses() or {}).get(c)
    if not a:
        return {"error": "no_analysis", "code": c}
    return {
        "code": c,
        "name": a.get("name"),
        "riskOk": a.get("riskOk"),
        "reviewedAt": a.get("reviewedAt"),
        "reason": a.get("reason"),
        "notes": a.get("notes"),
        "analysis": a.get("analysis"),
        "type": a.get("type"),
    }


def upsert_analysis(body: dict[str, Any] | None) -> dict[str, Any]:
    body = body or {}
    current = load_analyses() or {}
    if isinstance(body.get("analyses"), dict):
        save_analyses(body["analyses"])
        current = body["analyses"]
    elif isinstance(body.get("code"), str):
        code = body["code"]
        prev = current.get(code) or {}
        prev.update(body)
        current[code] = prev
        save_analyses(current)
    return {"success": True, "analyses": current}
