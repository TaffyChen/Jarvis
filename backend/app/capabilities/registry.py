"""能力注册表：供多 Agent / 未来 MCP 发现「有哪些能力」。"""
from __future__ import annotations

from typing import Any, Callable

from app.capabilities.knowledge import (
    delete_kb_document,
    get_kb_document,
    kb_overview,
    list_kb_documents,
    preview_kb_chunks,
    reindex_knowledge,
    save_kb_document,
)
from app.capabilities.mutate import (
    add_code,
    apply_memory_notes,
    apply_strategy_patch,
    remove_position,
    upsert_position,
)
from app.capabilities.query import (
    get_analysis,
    get_journal,
    get_market_overview,
    get_positions,
    get_quote,
    get_score,
    search_codes,
    search_knowledge,
    search_memory,
)

CALLABLES: dict[str, Callable[..., Any]] = {
    "search_knowledge": search_knowledge,
    "search_memory": search_memory,
    "search_codes": search_codes,
    "get_quote": get_quote,
    "get_score": get_score,
    "get_analysis": get_analysis,
    "get_positions": get_positions,
    "get_market_overview": get_market_overview,
    "get_journal": get_journal,
    "add_code": add_code,
    "upsert_position": upsert_position,
    "remove_position": remove_position,
    "apply_strategy_patch": apply_strategy_patch,
    "apply_memory_notes": apply_memory_notes,
    "list_kb_documents": list_kb_documents,
    "get_kb_document": get_kb_document,
    "save_kb_document": save_kb_document,
    "delete_kb_document": delete_kb_document,
    "preview_kb_chunks": preview_kb_chunks,
    "kb_overview": kb_overview,
    "reindex_knowledge": reindex_knowledge,
}

CAPABILITY_META: list[dict[str, Any]] = [
    {
        "name": "search_knowledge",
        "kind": "read",
        "summary": "检索本地纪律知识库与 analyses 索引",
        "params": {"query": "str", "top_k": "int?"},
    },
    {
        "name": "search_memory",
        "kind": "read",
        "summary": "检索对话沉淀认知卡片",
        "params": {"query": "str", "top_k": "int?"},
    },
    {
        "name": "search_codes",
        "kind": "read",
        "summary": "按股票名称或代码搜索 A 股/ETF",
        "params": {"query": "str", "limit": "int?"},
    },
    {
        "name": "get_quote",
        "kind": "read",
        "summary": "单标的实时行情缓存",
        "params": {"code": "str"},
    },
    {
        "name": "get_score",
        "kind": "read",
        "summary": "综合评分与关键因子",
        "params": {"code": "str"},
    },
    {
        "name": "get_analysis",
        "kind": "read",
        "summary": "利空复核与定性分析",
        "params": {"code": "str"},
    },
    {
        "name": "get_positions",
        "kind": "read",
        "summary": "全部持仓及现价",
        "params": {},
    },
    {
        "name": "get_market_overview",
        "kind": "read",
        "summary": "广度 / 海外 / 涨停摘要",
        "params": {},
    },
    {
        "name": "get_journal",
        "kind": "read",
        "summary": "最近日记",
        "params": {"limit": "int?"},
    },
    {
        "name": "add_code",
        "kind": "write",
        "summary": "加入观察池并写 analyses 底稿",
        "params": {"code": "str", "name": "str?", "type": "str?", "notes": "str?"},
        "hitl_recommended": True,
    },
    {
        "name": "upsert_position",
        "kind": "write",
        "summary": "写入/更新持仓",
        "params": {"code": "str", "buy_price": "number", "shares": "number", "name": "str?"},
        "hitl_recommended": True,
    },
    {
        "name": "remove_position",
        "kind": "write",
        "summary": "删除持仓（支持代码或名称；不移出观察池）",
        "params": {"code": "str"},
        "hitl_recommended": True,
    },
    {
        "name": "apply_strategy_patch",
        "kind": "write",
        "summary": "执行已确认的 strategy_patch",
        "params": {"patch": "object"},
        "hitl_recommended": True,
    },
    {
        "name": "apply_memory_notes",
        "kind": "write",
        "summary": "写入已确认的 memory_patch",
        "params": {"patch": "object", "source_question": "str?"},
        "hitl_recommended": True,
    },
    {
        "name": "list_kb_documents",
        "kind": "read",
        "summary": "列出 knowledge/*.md",
        "params": {},
    },
    {
        "name": "get_kb_document",
        "kind": "read",
        "summary": "读取一篇知识库 Markdown",
        "params": {"path": "str"},
    },
    {
        "name": "save_kb_document",
        "kind": "write",
        "summary": "新建或覆盖 knowledge 下的 Markdown",
        "params": {"path": "str", "content": "str", "create": "bool?"},
        "hitl_recommended": True,
    },
    {
        "name": "delete_kb_document",
        "kind": "write",
        "summary": "删除 knowledge 下的 Markdown",
        "params": {"path": "str"},
        "hitl_recommended": True,
    },
    {
        "name": "preview_kb_chunks",
        "kind": "read",
        "summary": "预览 Markdown 切块结果（不写索引）",
        "params": {"path": "str?", "content": "str?"},
    },
    {
        "name": "kb_overview",
        "kind": "read",
        "summary": "知识库状态：后端、embedding、文档列表",
        "params": {},
    },
    {
        "name": "reindex_knowledge",
        "kind": "write",
        "summary": "重建向量索引（local 或 Milvus）",
        "params": {},
        "hitl_recommended": True,
    },
]


def list_capabilities() -> list[dict[str, Any]]:
    return list(CAPABILITY_META)


def invoke(name: str, **kwargs: Any) -> Any:
    """统一调用入口（脚本 / 未来 MCP 可用）。"""
    fn = CALLABLES.get(name)
    if not fn:
        raise KeyError(f"unknown_capability:{name}")
    return fn(**kwargs)
