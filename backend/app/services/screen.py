"""盘后选股 / 竞价 / 板块资金。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.market.service import market


async def screen_top() -> dict[str, Any]:
    return await market.screen_top()


async def auction_top() -> dict[str, Any]:
    return await market.auction_top()


async def sector_flow() -> dict[str, Any]:
    if not market.sector_flow_cache.get("list"):
        await market.fetch_all_quotes()
    return market.sector_flow_cache
