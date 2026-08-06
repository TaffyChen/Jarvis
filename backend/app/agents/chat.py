"""站内对话入口：统一走 LangGraph 决策图，写入仍靠 HITL 补丁。"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.agents.graph.runner import run_decision_graph


async def ask_jarvis(
    question: str,
    history: list[dict] | None = None,
    session_id: int | None = None,
) -> dict[str, Any]:
    return await run_decision_graph(question, history, session_id=session_id)


async def ask_jarvis_stream(
    question: str,
    history: list[dict] | None = None,
    session_id: int | None = None,
) -> AsyncIterator[str]:
    """Yield SSE data lines。"""
    result = await ask_jarvis(question, history, session_id=session_id)
    answer = result["answer"]
    step = 48
    for i in range(0, len(answer), step):
        yield json.dumps({"type": "delta", "text": answer[i : i + step]}, ensure_ascii=False)
    yield json.dumps(
        {
            "type": "done",
            "sources": result["sources"],
            "patch": result["patch"],
            "memoryPatch": result["memoryPatch"],
            "memoriesUsed": result.get("memoriesUsed") or [],
            "toolTrace": result.get("toolTrace") or [],
            "retrieveQueries": result.get("retrieveQueries") or [],
            "orchestrator": result.get("orchestrator"),
            "model": result["model"],
            "sessionId": result.get("sessionId"),
        },
        ensure_ascii=False,
    )
