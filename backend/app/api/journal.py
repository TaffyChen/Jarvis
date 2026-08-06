"""HTTP：纪律日记。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.journal import add_journal, list_journal

router = APIRouter(prefix="/api", tags=["journal"])


@router.get("/journal")
async def get_journal(
    q: str = Query("", description="关键词：代码 / 名称 / 告警 / 动作 / 备注"),
    level: str = Query("", description="danger / warning / info"),
    code: str = Query("", description="精确代码，如 sz000636 或 000636"),
    limit: int | None = Query(None, ge=1, le=500),
):
    return {
        "journal": list_journal(
            limit=limit,
            q=q or None,
            level=level or None,
            code=code or None,
        )
    }


@router.post("/journal")
async def post_journal(body: dict):
    entry = body.get("entry") if isinstance(body.get("entry"), dict) else body
    return {"success": True, "journal": add_journal(entry if isinstance(entry, dict) else None)}
