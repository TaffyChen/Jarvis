"""HTTP：行情快照 / 选股 / 竞价 / 板块资金。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.services.quotes import indices_snapshot, klines_snapshot, quotes_snapshot, refresh_klines, refresh_quotes
from app.services.screen import auction_top, screen_top, sector_flow

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/quotes")
async def quotes():
    return quotes_snapshot()


@router.get("/market")
async def market_indices():
    return indices_snapshot()


@router.get("/klines")
async def klines():
    return klines_snapshot()


@router.get("/screen")
async def screen():
    return await screen_top()


@router.get("/auction")
async def auction():
    return await auction_top()


@router.get("/sector-flow")
async def sector_flow_api():
    return await sector_flow()


async def kick_quote_refresh():
    asyncio.create_task(refresh_quotes())
    asyncio.create_task(refresh_klines())
