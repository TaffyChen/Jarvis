"""
决策图对外入口
==============
chat API / ask_jarvis 最终会调用这里的 run_decision_graph。

职责：
1) ainvoke 编译好的图，拿到最终 GraphState
2) 规整 answer / sources / memories / patches / toolTrace
3) 轻量写入 conversations.json（便于事后复盘）
4) 返回与旧版 ask_jarvis 对齐的 dict，多一个 toolTrace、orchestrator=graph
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.graph.graph import get_decision_graph
from app.config import settings
from app.infra.storage import read_json, write_json


def _dedupe_sources(items: list[dict]) -> list[dict]:
    """预检索 + 工具回填可能重复，按 source/id 去重，最多留 12 条。"""
    seen = set()
    out = []
    for h in items or []:
        key = h.get("source") or h.get("id") or str(h)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out[:12]


async def run_decision_graph(question: str, history: list[dict] | None = None) -> dict[str, Any]:
    """跑完整张决策图，并打包成 API 响应。

    入参：
      question — 用户本轮问题
      history  — 可选历史消息（role/content）

    出参关键字段：
      answer / sources / patch / memoryPatch / memoriesUsed /
      toolTrace（过程） / orchestrator=\"graph\" / model
    """
    graph = get_decision_graph()
    # ainvoke：异步执行整张图，直到走到 END
    final = await graph.ainvoke(
        {
            "question": question,
            "history": history or [],
        }
    )

    answer = final.get("answer") or ""
    if not answer:
        # 兜底：若 answer 字段空了，尝试从 messages 里找最后一条纯文本 assistant
        for m in reversed(final.get("messages") or []):
            if m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
                answer = m["content"]
                break

    sources = _dedupe_sources(final.get("sources") or [])
    memories = _dedupe_sources(final.get("memories_used") or [])
    patch = final.get("patch")
    memory_patch = final.get("memory_patch")
    tool_trace = final.get("tool_trace") or []
    retrieve_queries = final.get("retrieve_queries") or []

    # 落盘对话流水（含 toolTrace），方便你打开 data/conversations.json 对照学习
    conv = read_json("conversations.json", [])
    conv.insert(
        0,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "answer": (answer or "")[:4000],
            "sources": [{"source": h.get("source"), "score": h.get("score")} for h in sources],
            "patch": patch,
            "memoryPatch": memory_patch,
            "memoriesUsed": [
                {"id": m.get("id"), "title": m.get("title"), "kind": m.get("kind")} for m in memories
            ],
            "toolTrace": [{"tool": t.get("tool"), "args": t.get("args")} for t in tool_trace],
            "retrieveQueries": retrieve_queries,
            "orchestrator": "graph",
        },
    )
    write_json("conversations.json", conv[:100])

    return {
        "answer": answer,
        "sources": sources,
        "patch": patch,
        "memoryPatch": memory_patch,
        "memoriesUsed": memories,
        "toolTrace": tool_trace,
        "retrieveQueries": retrieve_queries,
        "orchestrator": "graph",
        "model": final.get("model") or settings.llm_model,
    }
