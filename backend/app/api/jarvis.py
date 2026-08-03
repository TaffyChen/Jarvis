from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.jarvis.service import ask_jarvis, ask_jarvis_stream
from app.core.local_kb import Chunk, chunk_markdown, get_store
from app.core.storage import read_json, write_json
from app.config import settings

router = APIRouter(prefix="/api/jarvis", tags=["jarvis"])


class ChatIn(BaseModel):
    question: str = Field(min_length=1)
    history: list[dict] = Field(default_factory=list)


class PatchApplyIn(BaseModel):
    patch: dict
    accept: bool = True


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


@router.post("/patches/apply")
async def apply_patch(body: PatchApplyIn):
    """HITL：用户确认后落盘策略补丁。"""
    if not body.accept:
        return {"success": True, "applied": False}
    patch = body.patch or {}
    applied = []
    analyses = read_json("analyses.json", {})
    journal = read_json("journal.json", [])
    proposals = read_json("strategy_proposals.json", [])
    for p in patch.get("patches") or []:
        target = p.get("target")
        action = p.get("action")
        payload = p.get("payload") or {}
        code = p.get("code")
        if target == "analyses" and code:
            row = analyses.get(code) or {"code": code, "name": payload.get("name") or code}
            if action == "update_riskOk" and "riskOk" in payload:
                row["riskOk"] = payload["riskOk"]
                row["reviewedAt"] = datetime.now(timezone.utc).date().isoformat()
            if action == "add_note" and payload.get("notes"):
                row["notes"] = payload["notes"]
                row["reviewedAt"] = datetime.now(timezone.utc).date().isoformat()
            analyses[code] = row
            applied.append({"code": code, "action": action})
        elif target == "journal":
            journal.insert(
                0,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "info",
                    "msg": payload.get("msg") or patch.get("summary") or "Jarvis 提案",
                    "action": payload.get("action") or "策略更新",
                    "note": payload.get("note") or "",
                    "name": "Jarvis",
                    "code": code or "",
                },
            )
            applied.append({"target": "journal", "action": action})
        elif target == "rules":
            proposals.insert(
                0,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "summary": patch.get("summary"),
                    "payload": payload,
                    "status": "accepted",
                },
            )
            applied.append({"target": "rules", "action": action})
    write_json("analyses.json", analyses)
    write_json("journal.json", journal[:500])
    write_json("strategy_proposals.json", proposals[:200])
    return {"success": True, "applied": True, "items": applied}


@router.post("/kb/reindex")
async def reindex_kb():
    chunks: list[Chunk] = []
    # markdown knowledge
    for p in sorted(settings.knowledge_dir.glob("**/*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(chunk_markdown(text, source=str(p.relative_to(settings.knowledge_dir))))
    # analyses as docs
    analyses = read_json("analyses.json", {})
    for code, a in (analyses or {}).items():
        parts = [
            a.get("name") or code,
            a.get("reason") or "",
            a.get("notes") or "",
            " ".join(x.get("text") or "" for x in (a.get("analysis") or [])),
            f"riskOk={a.get('riskOk')} reviewedAt={a.get('reviewedAt')}",
        ]
        text = "\n".join(parts)
        chunks.append(
            Chunk(id=f"analysis:{code}", text=text, source=f"analyses/{code}", meta={"code": code})
        )
    store = get_store()
    store.rebuild(chunks)
    return {"success": True, "chunks": len(chunks)}
