"""HTTP：知识库维护（管理员）。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.core.deps import require_perm
from app.services import search_knowledge
from app.services.knowledge import (
    delete_kb_document,
    get_kb_document,
    kb_overview,
    list_kb_documents,
    preview_kb_chunks,
    reindex_knowledge,
    save_kb_document,
    upload_kb_document,
)

router = APIRouter(prefix="/api/jarvis", tags=["knowledge"])


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
