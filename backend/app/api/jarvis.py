"""HTTP：Jarvis 对话 / 沉淀 / 补丁。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.chat import ask_jarvis, ask_jarvis_stream
from app.services.conversations import list_conversations
from app.services.knowledge import reindex_knowledge
from app.services.memory import apply_memory_notes, list_memories
from app.services.patches import apply_strategy_patch
from app.services.quotes import refresh_klines, refresh_quotes

router = APIRouter(prefix="/api/jarvis", tags=["jarvis"])


class ChatIn(BaseModel):
    question: str = Field(min_length=1)
    history: list[dict] = Field(default_factory=list)


class PatchApplyIn(BaseModel):
    patch: dict
    accept: bool = True


class MemoryApplyIn(BaseModel):
    patch: dict
    accept: bool = True
    sourceQuestion: str = ""


@router.post("/chat")
async def chat(body: ChatIn):
    return await ask_jarvis(body.question, body.history)


@router.post("/chat/stream")
async def chat_stream(body: ChatIn):
    async def gen():
        async for chunk in ask_jarvis_stream(body.question, body.history):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/conversations")
async def conversations():
    return {"conversations": list_conversations()}


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
