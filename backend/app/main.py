from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import analyses as analyses_api
from app.api import auth as auth_api
from app.api import codes as codes_api
from app.api import health as health_api
from app.api import jarvis as jarvis_api
from app.api import journal as journal_api
from app.api import knowledge as knowledge_api
from app.api import market as market_api
from app.api import positions as positions_api
from app.api import services as services_api
from app.core.config import ROOT, settings
from app.infrastructure.kb.index import ensure_kb_ready
from app.infrastructure.persistence.identity import init_identity, resolve_session
from app.infrastructure.persistence.storage import init_storage
from app.services.quotes import (
    refresh_klines,
    refresh_market_aux,
    refresh_quotes,
    refresh_sector_flow,
)


async def _quote_loop():
    while True:
        await asyncio.sleep(settings.quote_interval_sec)
        try:
            await refresh_quotes()
        except Exception as e:
            print("[quotes]", e)


async def _sector_flow_loop():
    while True:
        await asyncio.sleep(max(15, int(settings.sector_flow_interval_sec)))
        try:
            await refresh_sector_flow()
        except Exception as e:
            print("[sector-flow]", e)


async def _market_aux_loop():
    while True:
        await asyncio.sleep(max(30, int(settings.market_aux_interval_sec)))
        try:
            await refresh_market_aux()
        except Exception as e:
            print("[market-aux]", e)


async def _kline_loop():
    while True:
        await asyncio.sleep(settings.kline_interval_sec)
        try:
            await refresh_klines()
        except Exception as e:
            print("[klines]", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    info = init_storage()
    print(f"[storage] backend={info.get('backend')} migrated={info.get('migrated')}", flush=True)
    ident = init_identity()
    print(f"[identity] {ident}", flush=True)
    kb = ensure_kb_ready()
    print(f"[kb] {kb}", flush=True)
    await refresh_quotes()
    await refresh_sector_flow()
    await refresh_market_aux()
    asyncio.create_task(refresh_klines())
    qtask = asyncio.create_task(_quote_loop())
    sftask = asyncio.create_task(_sector_flow_loop())
    atask = asyncio.create_task(_market_aux_loop())
    ktask = asyncio.create_task(_kline_loop())
    print(
        f"[poll] quotes={settings.quote_interval_sec}s "
        f"sector_flow={settings.sector_flow_interval_sec}s "
        f"aux={settings.market_aux_interval_sec}s "
        f"klines={settings.kline_interval_sec}s",
        flush=True,
    )
    yield
    qtask.cancel()
    sftask.cancel()
    atask.cancel()
    ktask.cancel()


app = FastAPI(title="Jarvis", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_PUBLIC_EXACT = {"/api/health", "/api/auth/login", "/"}
_PUBLIC_PREFIX = ("/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if path in _PUBLIC_EXACT or path.startswith(_PUBLIC_PREFIX) or path.startswith("/api/auth/"):
        return await call_next(request)
    if not path.startswith("/api/"):
        return await call_next(request)
    token = request.headers.get("x-jarvis-token") or ""
    user = resolve_session(token)
    if not user:
        return JSONResponse({"ok": False, "error": "未登录"}, status_code=401)
    request.state.user = user
    return await call_next(request)


app.include_router(health_api.router)
app.include_router(market_api.router)
app.include_router(positions_api.router)
app.include_router(analyses_api.router)
app.include_router(journal_api.router)
app.include_router(codes_api.router)
app.include_router(auth_api.router)
app.include_router(jarvis_api.router)
app.include_router(services_api.router)
app.include_router(knowledge_api.router)

_FRONTEND_DIST = ROOT / "frontend" / "dist"
if (_FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/")
    async def root():
        return {"name": "Jarvis", "docs": "/docs", "health": "/api/health"}
