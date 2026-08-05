"""HTTP：持仓。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.positions import list_positions_map, save_positions_map
from app.services.quotes import quotes_snapshot

router = APIRouter(prefix="/api", tags=["positions"])


@router.get("/positions")
async def get_positions():
    return {"positions": list_positions_map(), "lastUpdate": quotes_snapshot().get("lastUpdate")}


@router.post("/positions")
async def post_positions(body: dict):
    data = body.get("positions") if isinstance(body.get("positions"), dict) else body
    return save_positions_map(data if isinstance(data, dict) else None)
