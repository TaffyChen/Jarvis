"""HTTP：行情快照 / 选股 / 竞价 / 板块资金。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.quotes import indices_snapshot, klines_snapshot, quotes_snapshot, refresh_klines, refresh_quotes
from app.services.screen import analyze_screen_pick, auction_top, get_strategy_doc, screen_top, sector_flow

router = APIRouter(prefix="/api", tags=["market"])


class ScreenAnalyzeIn(BaseModel):
    strategyId: str = Field(min_length=1)
    code: str = Field(min_length=1)
    row: dict | None = None


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


@router.get("/screen/strategy-doc")
async def screen_strategy_doc(strategyId: str):
    return get_strategy_doc(strategyId)


@router.post("/screen/analyze")
async def screen_analyze(body: ScreenAnalyzeIn):
    return await analyze_screen_pick(
        strategy_id=body.strategyId,
        code=body.code,
        row=body.row,
    )


@router.get("/auction")
async def auction():
    return await auction_top()


@router.get("/sector-flow")
async def sector_flow_api():
    return await sector_flow()


async def kick_quote_refresh():
    asyncio.create_task(refresh_quotes())
    asyncio.create_task(refresh_klines())
