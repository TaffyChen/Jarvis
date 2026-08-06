"""HTTP：标的分析底稿。"""
from __future__ import annotations

from fastapi import APIRouter

from app.services.analyses import list_analyses, upsert_analysis

router = APIRouter(prefix="/api", tags=["analyses"])


@router.get("/analyses")
async def get_analyses():
    return list_analyses()


@router.post("/analyses")
async def post_analyses(body: dict):
    return upsert_analysis(body)
