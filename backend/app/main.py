from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import capabilities as capabilities_api
from app.api import auth as auth_api
from app.api import jarvis as jarvis_api
from app.api import market as market_api
from app.config import ROOT, settings
from app.infra.market.service import market
from app.infra.local_kb import ensure_kb_ready
from app.infra.identity import init_identity, resolve_session
from app.infra.storage import init_storage


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
    info = init_storage()
    print(f"[storage] backend={info.get('backend')} migrated={info.get('migrated')}", flush=True)
    ident = init_identity()
    print(f"[identity] {ident}", flush=True)
    kb = ensure_kb_ready()
    print(f"[kb] {kb}", flush=True)
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


app.include_router(market_api.router)
app.include_router(auth_api.router)
app.include_router(jarvis_api.router)
app.include_router(capabilities_api.router)

_FRONTEND_DIST = ROOT / "frontend" / "dist"
if (_FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/")
    async def root():
        return {"name": "Jarvis", "docs": "/docs", "health": "/api/health"}
