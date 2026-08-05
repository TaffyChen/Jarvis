from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.config import settings
from app.domain.codes import normalize_code
from app.infra.local_kb import kb_info
from app.infra.storage import read_json, storage_info, write_json
from app.infra.market.service import market
from app.capabilities import add_code
from app.capabilities.query import search_codes

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/health")
async def health():
    key = (settings.llm_api_key or "").strip()
    configured = bool(key) and "your-deepseek-key" not in key and key != "missing"
    return {
        "ok": True,
        "service": "jarvis",
        "quotes": len(market.quote_cache),
        "lastUpdate": market.last_update,
        "llmConfigured": configured,
        "storage": storage_info(),
        "knowledge": kb_info(),
    }


@router.get("/quotes")
async def quotes():
    return {
        "quotes": market.quote_cache,
        "breadth": market.breadth,
        "marketBreadth": market.market_breadth,
        "overseas": market.overseas,
        "limitUpStats": market.limit_up_stats,
        "lastUpdate": market.last_update,
    }


@router.get("/market")
async def market_indices():
    return {"indices": market.index_cache, "breadth": market.breadth, "lastUpdate": market.last_update}


@router.get("/klines")
async def klines():
    return {"klines": market.kline_cache, "indexKlines": {}, "lastUpdate": market.last_kline_update}


@router.get("/positions")
async def get_positions():
    return {"positions": read_json("positions.json", {}), "lastUpdate": market.last_update}


@router.post("/positions")
async def save_positions(body: dict):
    data = body.get("positions") if isinstance(body.get("positions"), dict) else body
    if isinstance(data, dict):
        write_json("positions.json", data)
    return {"success": True}


@router.get("/analyses")
async def get_analyses():
    return {
        "analyses": read_json("analyses.json", {}),
        "staleDays": settings.analysis_stale_days,
    }


@router.post("/analyses")
async def save_analyses(body: dict):
    current = read_json("analyses.json", {})
    if isinstance(body.get("analyses"), dict):
        write_json("analyses.json", body["analyses"])
        current = body["analyses"]
    elif isinstance(body.get("code"), str):
        code = body["code"]
        prev = current.get(code) or {}
        prev.update(body)
        current[code] = prev
        write_json("analyses.json", current)
    return {"success": True, "analyses": current}


@router.get("/journal")
async def get_journal():
    return {"journal": read_json("journal.json", [])}


@router.post("/journal")
async def add_journal(body: dict):
    entry = body.get("entry") if isinstance(body.get("entry"), dict) else body
    journal = read_json("journal.json", [])
    if isinstance(entry, dict):
        journal.insert(0, entry)
        write_json("journal.json", journal[:500])
    return {"success": True, "journal": journal}


@router.get("/codes/search")
async def codes_search(q: str = "", limit: int = 8):
    rows = await search_codes(q, limit=limit)
    return {"query": q, "results": rows}


@router.post("/codes/add")
async def add_codes(body: dict):
    codes = body.get("codes") or []
    added = 0
    need_quotes = False
    for raw in codes:
        c = normalize_code(raw) if raw else ""
        if not c:
            c = str(raw or "").strip().lower()
        if not c:
            continue
        r = add_code(c, save=True)
        if r.get("added_to_universe"):
            added += 1
        if r.get("need_quotes"):
            need_quotes = True
    if need_quotes:
        asyncio.create_task(market.fetch_all_quotes())
        asyncio.create_task(market.fetch_all_klines())
    return {"success": True, "added": added, "total": len(market.stock_codes)}


@router.post("/codes/remove")
async def remove_codes(body: dict):
    codes = body.get("codes") or []
    removed = 0
    for c in codes:
        if c in market.stock_codes:
            market.stock_codes.remove(c)
            market.quote_cache.pop(c, None)
            market.kline_cache.pop(c, None)
            removed += 1
    if removed:
        market.save_codes()
    return {"success": True, "removed": removed, "total": len(market.stock_codes)}


@router.get("/screen")
async def screen():
    return await market.screen_top()


@router.get("/auction")
async def auction():
    return await market.auction_top()


@router.get("/sector-flow")
async def sector_flow():
    # Warm start: if cache is empty after service boot, fetch once on demand.
    if not market.sector_flow_cache.get("list"):
        await market.fetch_all_quotes()
    return market.sector_flow_cache
