"""
LangGraph 多工具决策图 · 图编排（最重要的学习文件）
================================================
流程一览：

    START
      │
      ▼
  bootstrap   RAG 预检索（多路召回 + rerank）并注入原文，组装 messages
      │
      ▼
    agent     调大模型：可能直接回答，也可能提出 tool_calls
      │
      ├── 有 tool_calls ──► tools ──►（执行工具，写回 messages）──► 再回到 agent
      │
      └── 无 tool_calls ──► END（answer 已写好）

边界控制：
  - 工具全部只读（见 tools.py）
  - tool_rounds >= JARVIS_GRAPH_MAX_TOOL_ROUNDS 时不再下发 tools，强制收束
  - 写入只能靠回答末尾的 patch 提案 + 前端 HITL

例子（用户问「sz300408 还能持有吗」）见：`docs/decision-graph.md`。
"""
from __future__ import annotations

import json
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.graph.state import GraphState
from app.agents.graph.tools import OPENAI_TOOLS, run_tool
from app.agents.common import (
    extract_typed_json,
    remember_intent,
    add_code_intent,
    add_position_intent,
    remove_position_intent,
)
from app.core.config import settings
from app.services.rag import format_retrieval_block, retrieve_for_dialog
from app.domain.codes import normalize_code
from app.infrastructure.llm import SYSTEM_PROMPT, get_llm_client
import re

# 在通用 SYSTEM_PROMPT 上追加「工具模式」纪律，告诉模型何时该调工具、何时只能提案写入。
GRAPH_SYSTEM = (
    SYSTEM_PROMPT
    + """

你处于「多工具决策图 + RAG」模式：
- 用户消息里已注入预检索纪律/沉淀。回答纪律问题先用这些原文，并在依据里点名文档（如 五灯仓位.md）。
- 需要行情、评分、持仓、分析时再调工具；不要编造工具未返回的数据，也不要编造未检索到的规则。
- 预检索不够时才再调 search_knowledge / search_memory，并换更具体的检索词。
- 工具都是只读的；写入仍只能通过回答末尾的 strategy_patch / memory_patch 提案。
- 用户要加观察池/持仓时：本轮必须附 ```json strategy_patch```，禁止只口头说「点采纳才会写入」却不附 JSON。
- 尽量少轮工具调用（通常 1～3 轮）后给出可执行结论：先结论，再依据。
"""
)


def bootstrap(state: GraphState) -> dict:
    """节点 1：启动准备。

    做两件事：
    1) 轻量预检索（知识库 + 沉淀），让模型一开始就有线索；
    2) 组装 messages（system + 历史 + 当前问题），并初始化计数器/轨迹。

    返回的 dict 会合并进 GraphState。
    """
    question = state.get("question") or ""
    history = state.get("history") or []

    rag = retrieve_for_dialog(question, history, top_k=5)
    sources = rag.get("sources") or []
    memories = rag.get("memories") or []

    hint = ""
    if remember_intent(question):
        hint += (
            "\n用户明确要求沉淀/记住：请在最终回答输出 memory_patch；"
            "信息不足先追问。"
        )
    if add_code_intent(question) or add_position_intent(question):
        # 从问题里捞出疑似代码，帮助模型写对前缀
        digits = re.findall(r"(\d{5,6})", question)
        norms = [normalize_code(d) for d in digits]
        norms = [c for c in norms if c]
        hint += (
            "\n用户要求写入本地系统（添加标的/持仓）。"
            "必须在最终回答输出 strategy_patch（```json``` 代码块）："
            "加观察池用 target=codes action=add；"
            "加持仓用 target=positions action=upsert（需 buyPrice 与 shares）。"
            "禁止只口头承诺「会输出补丁/点采纳」；本轮就要附上 JSON。"
            "未经界面确认不要声称已添加。"
        )
        if norms:
            hint += f"\n已识别代码候选：{', '.join(norms)}（请直接用于 patch.code）。"

    if remove_position_intent(question):
        digits = re.findall(r"(\d{5,6})", question)
        norms = [normalize_code(d) for d in digits]
        norms = [c for c in norms if c]
        hint += (
            "\n用户要求删除持仓。"
            "请先调用 get_positions（必要时再按名称匹配），"
            "最终回答必须输出 strategy_patch："
            "target=positions action=remove，code 用规范代码（如 sz000333），"
            "payload 可带 name。"
            "未经界面确认不要声称已删除。"
        )
        if norms:
            hint += f"\n已识别代码候选：{', '.join(norms)}（请直接用于 patch.code）。"

    bootstrap_note = (
        format_retrieval_block(rag)
        + "\n\n### 编排提示\n"
        + "行情/持仓/评分请调工具。纪律已在上方，不必重复 search_knowledge，除非明显不够。\n"
        + hint
    )

    messages: list[dict] = [{"role": "system", "content": GRAPH_SYSTEM}]
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"{question}\n\n{bootstrap_note}",
        }
    )
    rag_trace = {
        "tool": "rag_retrieve",
        "args": {"queries": rag.get("queries") or [question], "rerank": (rag.get("rerank") or {}).get("enabled")},
        "resultPreview": f"knowledge={len(sources)} memory={len(memories)}",
    }
    return {
        "messages": messages,
        "tool_rounds": 0,
        "tool_trace": [rag_trace],
        "retrieve_queries": rag.get("queries") or [],
        "sources": [
            {
                "source": h.get("source"),
                "score": h.get("score"),
                "text": (h.get("text") or "")[:240],
                "reranked": h.get("reranked"),
            }
            for h in sources
        ],
        "memories_used": [
            {"id": m.get("id"), "title": m.get("title"), "kind": m.get("kind"), "content": m.get("content")}
            for m in memories
        ],
        "answer": "",
        "patch": None,
        "memory_patch": None,
        "model": settings.llm_model,
        "error": None,
    }


async def agent(state: GraphState) -> dict:
    """节点 2：调用大模型（思考 / 决定调哪些工具 / 或直接给结论）。

    两种出口：
    A) 返回带 tool_calls 的 assistant message → 路由去 tools
    B) 返回纯文本 answer → 解析 patch，路由去 END
    """
    if not settings.llm_api_key or "your-deepseek-key" in settings.llm_api_key:
        # 无 Key：无法真正编排，直接用预检索数量提示用户配置。
        src = state.get("sources") or []
        mem = state.get("memories_used") or []
        answer = (
            "尚未配置有效的 LLM_API_KEY，决策图无法调用模型。\n"
            f"预检索知识 {len(src)} 条、沉淀 {len(mem)} 条。"
        )
        return {"answer": answer, "messages": state.get("messages") or [], "model": None}

    client = get_llm_client()
    messages = list(state.get("messages") or [])
    rounds = int(state.get("tool_rounds") or 0)
    max_rounds = max(1, int(settings.jarvis_graph_max_tool_rounds))

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.3,
    }
    # 【边界·强制收束】已用满工具轮次时，不再把 tools 传给模型，
    # 模型只能输出自然语言结论，避免无限「再查一轮」。
    if rounds < max_rounds:
        kwargs["tools"] = OPENAI_TOOLS
        kwargs["tool_choice"] = "auto"

    resp = await client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content or "",
    }

    # DeepSeek / OpenAI 兼容：模型若要调工具，会在 tool_calls 里给出函数名与参数 JSON。
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in tool_calls
        ]
    messages.append(assistant_msg)

    if not tool_calls:
        # 收束：没有工具调用 = 本轮最终回答。
        answer = msg.content or ""
        patch, memory_patch = extract_typed_json(answer)
        return {
            "messages": messages,
            "answer": answer,
            "patch": patch,
            "memory_patch": memory_patch,
            "model": settings.llm_model,
        }
    # 还有工具要跑：先把带 tool_calls 的消息写回 state，交给 run_tools。
    return {"messages": messages, "model": settings.llm_model}


def run_tools(state: GraphState) -> dict:
    """节点 3：执行模型点名的工具，把结果以 role=tool 写回 messages。

    同时：
    - 追加 tool_trace（前端可见过程）
    - tool_rounds += 1（逼近收束上限）
    - 若是 search_*，顺带回填 sources / memories_used
    """
    messages = list(state.get("messages") or [])
    if not messages:
        return {}
    last = messages[-1]
    tool_calls = last.get("tool_calls") or []
    trace = list(state.get("tool_trace") or [])
    sources = list(state.get("sources") or [])
    memories = list(state.get("memories_used") or [])

    for tc in tool_calls:
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}

        # 真正执行本地只读函数（见 tools.py）
        result = run_tool(name, args)

        # OpenAI 协议：每条 tool 结果必须带上对应的 tool_call_id
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id") or name,
                "content": result[:6000],
            }
        )
        # 【可观测】记录轨迹，不把全文塞进前端，只留预览
        trace.append({"tool": name, "args": args, "resultPreview": result[:400]})

        if name == "search_knowledge":
            try:
                for h in json.loads(result) or []:
                    if isinstance(h, dict) and h.get("source"):
                        sources.append(
                            {
                                "source": h.get("source"),
                                "score": h.get("score"),
                                "text": (h.get("text") or "")[:240],
                            }
                        )
            except Exception:
                pass
        if name == "search_memory":
            try:
                for h in json.loads(result) or []:
                    if isinstance(h, dict):
                        memories.append(
                            {
                                "id": h.get("id"),
                                "title": h.get("title"),
                                "kind": h.get("kind"),
                                "content": h.get("content"),
                            }
                        )
            except Exception:
                pass

    return {
        "messages": messages,
        "tool_trace": trace,
        "tool_rounds": int(state.get("tool_rounds") or 0) + 1,
        "sources": sources,
        "memories_used": memories,
    }


def route_after_agent(state: GraphState) -> Literal["tools", "end"]:
    """条件边：看 agent 最新一条消息有没有 tool_calls。

    - 有 → 去 tools 节点执行
    - 无 → END（此时 state.answer 应已由 agent 写好）
    """
    messages = state.get("messages") or []
    if not messages:
        return "end"
    last = messages[-1]
    if last.get("role") == "assistant" and last.get("tool_calls"):
        return "tools"
    return "end"


def build_decision_graph():
    """把节点和边编译成可 ainvoke 的图对象。

    边的含义：
    - START → bootstrap → agent
    - agent ──(条件)──► tools 或 END
    - tools → agent   （形成多步循环）
    """
    g = StateGraph(GraphState)
    g.add_node("bootstrap", bootstrap)
    g.add_node("agent", agent)
    g.add_node("tools", run_tools)
    g.add_edge(START, "bootstrap")
    g.add_edge("bootstrap", "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()


_compiled = None


def get_decision_graph():
    """进程内单例：避免每次对话重新 compile。"""
    global _compiled
    if _compiled is None:
        _compiled = build_decision_graph()
    return _compiled


# 完整走查例子（含表格与验证步骤）见：docs/decision-graph.md
