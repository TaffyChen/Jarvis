"""HTTP：观察池搜索 / 加减。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.services.codes import add_codes, remove_codes, search_codes
from app.services.quotes import refresh_klines, refresh_quotes

router = APIRouter(prefix="/api/codes", tags=["codes"])


@router.get("/search")
async def codes_search(q: str = "", limit: int = 8):
    rows = await search_codes(q, limit=limit)
    return {"query": q, "results": rows}


@router.post("/add")
async def codes_add(body: dict):
    result = add_codes(body.get("codes") or [])
    if result.get("need_quotes"):
        asyncio.create_task(refresh_quotes())
        asyncio.create_task(refresh_klines())
    return result


@router.post("/remove")
async def codes_remove(body: dict):
    return remove_codes(body.get("codes") or [])
