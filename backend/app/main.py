from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jarvis as jarvis_api
from app.api import market as market_api
from app.config import settings
from app.services.market.service import market


async def _quote_loop():
    while True:
        try:
            await market.fetch_all_quotes()
        except Exception as e:
            print("[quotes]", e)
        await asyncio.sleep(settings.quote_interval_sec)


async def _kline_loop():
    while True:
        try:
            await market.fetch_all_klines()
        except Exception as e:
            print("[klines]", e)
        await asyncio.sleep(settings.kline_interval_sec)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await market.fetch_all_quotes()
    asyncio.create_task(market.fetch_all_klines())
    qtask = asyncio.create_task(_quote_loop())
    ktask = asyncio.create_task(_kline_loop())
    yield
    qtask.cancel()
    ktask.cancel()


app = FastAPI(title="Jarvis", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(market_api.router)
app.include_router(jarvis_api.router)


@app.get("/")
async def root():
    return {"name": "Jarvis", "docs": "/docs", "health": "/api/health"}
