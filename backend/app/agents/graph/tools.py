"""
决策图可调用工具（适配层）
========================
这里不再实现业务逻辑，只做两件事：
1) 调用 app.services（共用服务层）
2) 把结果 json.dumps，并提供 OpenAI Function Calling schema

【边界】本文件暴露给模型的仍是只读工具。
写入（加标的/持仓）走 strategy_patch → HITL → services.apply_strategy_patch。
"""
from __future__ import annotations

import json
from typing import Any, Callable

from app.services import analyses, journal, knowledge, memory, positions, quotes

JsonFn = Callable[..., str]


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def tool_search_knowledge(query: str, top_k: int = 5) -> str:
    return _dumps(knowledge.search_knowledge(query, top_k=top_k))


def tool_search_memory(query: str, top_k: int = 5) -> str:
    return _dumps(memory.search_memories(query, top_k=top_k))


def tool_get_quote(code: str) -> str:
    return _dumps(quotes.get_quote(code))


def tool_get_score(code: str) -> str:
    return _dumps(quotes.get_score(code))


def tool_get_analysis(code: str) -> str:
    return _dumps(analyses.get_analysis(code))


def tool_get_positions() -> str:
    return _dumps(positions.get_positions())


def tool_get_market_overview() -> str:
    return _dumps(quotes.get_market_overview())


def tool_get_journal(limit: int = 5, q: str = "", level: str = "", code: str = "") -> str:
    return _dumps(journal.get_journal(limit=limit, q=q, level=level, code=code))


TOOL_IMPLS: dict[str, JsonFn] = {
    "search_knowledge": tool_search_knowledge,
    "search_memory": tool_search_memory,
    "get_quote": tool_get_quote,
    "get_score": tool_get_score,
    "get_analysis": tool_get_analysis,
    "get_positions": tool_get_positions,
    "get_market_overview": tool_get_market_overview,
    "get_journal": tool_get_journal,
}

OPENAI_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "补充检索纪律知识库。预检索结果已在用户消息中；仅当依据不足或要换检索词时再调。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索语句"},
                    "top_k": {"type": "integer", "description": "返回条数，默认5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "检索用户确认过的对话沉淀认知卡片。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "查询单只股票/ETF 实时行情。",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "如 sz300408"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_score",
            "description": "计算标的综合评分与关键因子。",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_analysis",
            "description": "读取标的利空复核、备注与定性分析。",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_positions",
            "description": "列出当前全部持仓及现价。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": "市场广度、海外指数、涨停相关摘要。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_journal",
            "description": "纪律日记：可按关键词、级别、代码检索最近留痕。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最多返回条数，默认 5，上限 20"},
                    "q": {"type": "string", "description": "关键词，匹配代码/名称/告警/动作/备注"},
                    "level": {"type": "string", "description": "danger / warning / info"},
                    "code": {"type": "string", "description": "标的代码，如 000636 或 sz000636"},
                },
            },
        },
    },
]


def run_tool(name: str, arguments: dict | str | None) -> str:
    fn = TOOL_IMPLS.get(name)
    if not fn:
        return _dumps({"error": f"unknown_tool:{name}"})
    args = arguments or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except Exception:
            args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        return fn(**args)
    except TypeError as e:
        return _dumps({"error": "bad_args", "detail": str(e), "tool": name})
    except Exception as e:
        return _dumps({"error": "tool_failed", "detail": str(e), "tool": name})
