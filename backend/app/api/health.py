"""HTTP：健康检查。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.quotes import health_snapshot

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return health_snapshot()
