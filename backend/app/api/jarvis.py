"""HTTP：Jarvis 对话 / 沉淀 / 补丁。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.chat import ask_jarvis, ask_jarvis_stream
from app.services.conversations import (
    create_chat_session,
    get_chat_session,
    list_chat_sessions,
    list_conversations,
)
from app.services.knowledge import reindex_knowledge
from app.services.memory import apply_memory_notes, list_memories
from app.services.patches import apply_strategy_patch
from app.services.quotes import refresh_klines, refresh_quotes

router = APIRouter(prefix="/api/jarvis", tags=["jarvis"])


class ChatIn(BaseModel):
    question: str = Field(min_length=1)
    history: list[dict] = Field(default_factory=list)
    sessionId: int | None = None


class PatchApplyIn(BaseModel):
    patch: dict
    accept: bool = True


class MemoryApplyIn(BaseModel):
    patch: dict
    accept: bool = True
    sourceQuestion: str = ""


class SessionCreateIn(BaseModel):
    title: str = ""


@router.post("/chat")
async def chat(body: ChatIn):
    return await ask_jarvis(body.question, body.history, session_id=body.sessionId)


@router.post("/chat/stream")
async def chat_stream(body: ChatIn):
    async def gen():
        async for chunk in ask_jarvis_stream(body.question, body.history, session_id=body.sessionId):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/conversations")
async def conversations():
    return {"conversations": list_conversations()}


@router.get("/chat/sessions")
async def chat_sessions():
    return {"sessions": list_chat_sessions()}


@router.post("/chat/sessions")
async def chat_sessions_create(body: SessionCreateIn | None = None):
    opts = body or SessionCreateIn()
    return {"session": create_chat_session(opts.title or "")}


@router.get("/chat/sessions/{session_id}")
async def chat_session_detail(session_id: int):
    data = get_chat_session(session_id)
    if not data:
        return JSONResponse({"error": "session_not_found"}, status_code=404)
    return data


@router.get("/memories")
async def get_memories():
    return {"memories": list_memories(200)}


@router.post("/memories/apply")
async def memories_apply(body: MemoryApplyIn):
    if not body.accept:
        return {"success": True, "applied": 0, "skipped": True}
    result = apply_memory_notes(body.patch or {}, source_question=body.sourceQuestion)
    if result.get("applied"):
        await asyncio.to_thread(reindex_knowledge)
    return result


@router.post("/patches/apply")
async def apply_patch(body: PatchApplyIn):
    if not body.accept:
        return {"success": True, "applied": False}
    result = apply_strategy_patch(body.patch or {})
    if result.get("need_quotes"):
        asyncio.create_task(refresh_quotes())
        asyncio.create_task(refresh_klines())
    return result


class ReviewGenerateIn(BaseModel):
    refreshSnapshot: bool = True
    briefDate: str | None = None
    baseVersionId: int | None = None
    markFinal: bool = False


class ReviewCommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.get("/review/snapshot")
async def review_snapshot():
    """实时盘面采集（不落库）。"""
    from app.services.review import build_daily_review_snapshot
    from app.services.screen import sector_flow

    await sector_flow()
    return {"snapshot": build_daily_review_snapshot(), "live": True}


@router.get("/review/days")
async def review_days():
    from app.services.review import list_brief_days

    return {"days": list_brief_days()}


@router.get("/review/days/{brief_date}")
async def review_day_get(brief_date: str):
    from app.services.review import get_brief_day

    row = get_brief_day(brief_date)
    if not row:
        return JSONResponse({"error": "day_not_found"}, status_code=404)
    return {"day": row}


@router.get("/review/versions/{version_id}")
async def review_version_get(version_id: int):
    from app.services.review import get_brief_version

    row = get_brief_version(version_id)
    if not row:
        return JSONResponse({"error": "version_not_found"}, status_code=404)
    return {"version": row}


@router.post("/review/generate")
async def review_generate(body: ReviewGenerateIn | None = None):
    from app.services.review import generate_brief

    opts = body or ReviewGenerateIn()
    try:
        return await generate_brief(
            refresh_snapshot=bool(opts.refreshSnapshot),
            brief_date=opts.briefDate,
            base_version_id=opts.baseVersionId,
            mark_final=bool(opts.markFinal),
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/review/versions/{version_id}/comments")
async def review_version_comment(version_id: int, body: ReviewCommentIn):
    from app.services.review import add_brief_comment

    row = add_brief_comment(version_id, body.text)
    if not row:
        return JSONResponse({"error": "version_not_found"}, status_code=404)
    return {"version": row}


@router.post("/review/versions/{version_id}/final")
async def review_version_final(version_id: int):
    from app.services.review import mark_brief_final

    row = mark_brief_final(version_id)
    if not row:
        return JSONResponse({"error": "version_not_found"}, status_code=404)
    return {"version": row}

