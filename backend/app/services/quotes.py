"""行情快照与评分。"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.domain.codes import normalize_code
from app.infrastructure.kb.index import kb_info
from app.infrastructure.market.service import market
from app.infrastructure.persistence.storage import storage_info


def get_quote(code: str) -> dict[str, Any]:
    c = normalize_code(code) or (code or "").strip().lower()
    q = market.quote_cache.get(c)
    if not q:
        return {"error": "unknown_or_no_quote", "code": c}
    keys = (
        "code", "name", "price", "changePct", "volume", "amount",
        "liangbi", "weibi", "peTTM", "pb", "high", "low", "open",
    )
    return {k: q.get(k) for k in keys}


def get_score(code: str) -> dict[str, Any]:
    c = normalize_code(code) or (code or "").strip().lower()
    q = market.quote_cache.get(c) or {}
    k = market.kline_cache.get(c) or {}
    if not q:
        return {"error": "no_quote", "code": c}
    score = market.final_score(q, k) if k else market.score_quote(q)
    return {
        "code": c,
        "name": q.get("name"),
        "score": score,
        "price": q.get("price"),
        "changePct": q.get("changePct"),
        "ma20": k.get("ma20"),
        "change20d": k.get("change20d"),
        "liangbi": q.get("liangbi"),
        "weibi": q.get("weibi"),
        "peTTM": q.get("peTTM"),
    }


def get_market_overview() -> dict[str, Any]:
    mb = market.market_breadth or {}
    ov = market.overseas or {}
    lu = getattr(market, "limit_up_stats", None) or {}
    return {
        "breadth": mb,
        "overseas": ov,
        "limitUp": {
            "today": (lu.get("today") if isinstance(lu, dict) else None),
            "summary": {
                k: lu.get(k)
                for k in ("upCount", "downCount", "limitUpCount")
                if isinstance(lu, dict)
            },
        },
    }


def quotes_snapshot() -> dict[str, Any]:
    from app.services.sentiment import sentiment_history_snapshot

    return {
        "quotes": market.quote_cache,
        "breadth": market.breadth,
        "marketBreadth": market.market_breadth,
        "overseas": market.overseas,
        "limitUpStats": market.limit_up_stats,
        "marketTurnover": market.market_turnover,
        "sentimentHistory": sentiment_history_snapshot(),
        "lastUpdate": market.last_update,
    }


def indices_snapshot() -> dict[str, Any]:
    from app.services.sentiment import sentiment_history_snapshot

    return {
        "indices": market.index_cache,
        "breadth": market.breadth,
        "marketTurnover": market.market_turnover,
        "sentimentHistory": sentiment_history_snapshot(),
        "lastUpdate": market.last_update,
    }


def klines_snapshot() -> dict[str, Any]:
    return {"klines": market.kline_cache, "indexKlines": {}, "lastUpdate": market.last_kline_update}


def health_snapshot() -> dict[str, Any]:
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


async def refresh_quotes() -> None:
    await market.fetch_all_quotes()


async def refresh_market_aux() -> None:
    await market.fetch_market_aux()


async def refresh_sector_flow() -> None:
    await market.fetch_sector_flow()


async def refresh_klines() -> None:
    await market.fetch_all_klines()
