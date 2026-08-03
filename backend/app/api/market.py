from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.core.storage import read_json, write_json
from app.services.market.service import market

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


@router.post("/codes/add")
async def add_codes(body: dict):
    codes = body.get("codes") or []
    added = 0
    for c in codes:
        if c and c not in market.stock_codes:
            market.stock_codes.append(c)
            added += 1
    if added:
        market.save_codes()
    return {"success": True, "added": added, "total": len(market.stock_codes)}
