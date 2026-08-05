"""HTTP：Jarvis 对话 / 沉淀 / 补丁 / 知识库维护。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import require_perm

from app.agents.chat import ask_jarvis, ask_jarvis_stream
from app.capabilities import apply_memory_notes, apply_strategy_patch, search_knowledge
from app.capabilities.knowledge import (
    delete_kb_document,
    get_kb_document,
    kb_overview,
    list_kb_documents,
    preview_kb_chunks,
    reindex_knowledge,
    save_kb_document,
    upload_kb_document,
)
from app.domain.memory import list_memories
from app.infra.market.service import market
from app.infra.storage import read_json

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


class KbDocIn(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""
    create: bool = False


class KbPreviewIn(BaseModel):
    path: str = ""
    content: str | None = None


class KbSearchIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 5


def _kb_error(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc) or "文件不存在") from exc
    if isinstance(exc, FileExistsError):
        raise HTTPException(status_code=409, detail=str(exc) or "文件已存在") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


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
    return {"conversations": read_json("conversations.json", [])}


@router.get("/memories")
async def get_memories():
    return {"memories": list_memories(200)}


@router.post("/memories/apply")
async def memories_apply(body: MemoryApplyIn):
    if not body.accept:
        return {"success": True, "applied": 0, "skipped": True}
    # 站内写入采用 HITL：只有 accept=true 才真正落盘。
    result = apply_memory_notes(body.patch or {}, source_question=body.sourceQuestion)
    if result.get("applied"):
        await asyncio.to_thread(reindex_knowledge)
    return result


@router.post("/patches/apply")
async def apply_patch(body: PatchApplyIn):
    if not body.accept:
        return {"success": True, "applied": False}
    # strategy_patch 是“提案”；该接口是“确认执行”入口。
    result = apply_strategy_patch(body.patch or {})
    if result.get("need_quotes"):
        asyncio.create_task(market.fetch_all_quotes())
        asyncio.create_task(market.fetch_all_klines())
    return result


@router.get("/kb")
async def kb_status(_user=Depends(require_perm("kb.manage"))):
    return kb_overview()


@router.get("/kb/documents")
async def kb_documents(_user=Depends(require_perm("kb.manage"))):
    return {"documents": list_kb_documents()}


@router.get("/kb/document")
async def kb_document(path: str = Query(min_length=1), _user=Depends(require_perm("kb.manage"))):
    try:
        return get_kb_document(path)
    except Exception as e:
        _kb_error(e)


@router.put("/kb/document")
async def kb_save(body: KbDocIn, _user=Depends(require_perm("kb.manage"))):
    try:
        return save_kb_document(body.path, body.content, create=body.create)
    except Exception as e:
        _kb_error(e)


@router.post("/kb/upload")
async def kb_upload(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    _user=Depends(require_perm("kb.manage")),
):
    try:
        data = await file.read()
        return await asyncio.to_thread(
            upload_kb_document,
            filename=file.filename or "",
            data=data,
            overwrite=overwrite,
        )
    except Exception as e:
        _kb_error(e)


@router.delete("/kb/document")
async def kb_delete(path: str = Query(min_length=1), _user=Depends(require_perm("kb.manage"))):
    try:
        return delete_kb_document(path)
    except Exception as e:
        _kb_error(e)


@router.post("/kb/preview")
async def kb_preview(body: KbPreviewIn, _user=Depends(require_perm("kb.manage"))):
    try:
        return preview_kb_chunks(path=body.path or None, content=body.content)
    except Exception as e:
        _kb_error(e)


@router.post("/kb/search")
async def kb_search(body: KbSearchIn, _user=Depends(require_perm("kb.manage"))):
    return {"hits": search_knowledge(body.query, top_k=body.top_k)}


@router.post("/kb/reindex")
async def reindex_kb(_user=Depends(require_perm("kb.reindex"))):
    return await asyncio.to_thread(reindex_knowledge)
