"""服务注册表：供 Agent / MCP / HTTP 发现并调用。"""
from __future__ import annotations

from typing import Any, Callable

from app.services.analyses import get_analysis
from app.services.codes import add_code, search_codes
from app.services.journal import get_journal
from app.services.knowledge import (
    delete_kb_document,
    get_kb_document,
    kb_overview,
    list_kb_documents,
    preview_kb_chunks,
    reindex_knowledge,
    save_kb_document,
    search_knowledge,
    upload_kb_document,
)
from app.services.memory import apply_memory_notes, search_memories
from app.services.patches import apply_strategy_patch
from app.services.positions import get_positions, remove_position, upsert_position
from app.services.quotes import get_market_overview, get_quote, get_score

CALLABLES: dict[str, Callable[..., Any]] = {
    "search_knowledge": search_knowledge,
    "search_memory": search_memories,
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
    "upload_kb_document": upload_kb_document,
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
        "summary": "读取观察池内实时行情摘要",
        "params": {"code": "str"},
    },
    {
        "name": "get_score",
        "kind": "read",
        "summary": "综合评分与量价字段",
        "params": {"code": "str"},
    },
    {
        "name": "get_analysis",
        "kind": "read",
        "summary": "标的分析底稿与利空复核",
        "params": {"code": "str"},
    },
    {
        "name": "get_positions",
        "kind": "read",
        "summary": "当前持仓列表",
        "params": {},
    },
    {
        "name": "get_market_overview",
        "kind": "read",
        "summary": "市场宽度 / 外围 / 涨停摘要",
        "params": {},
    },
    {
        "name": "get_journal",
        "kind": "read",
        "summary": "纪律日记最近条目，可按关键词/级别/代码检索",
        "params": {"limit": "int?", "q": "str?", "level": "str?", "code": "str?"},
    },
    {
        "name": "add_code",
        "kind": "write",
        "summary": "加入观察池并补分析底稿",
        "params": {"code": "str", "name": "str?", "type": "str?", "notes": "str?"},
    },
    {
        "name": "upsert_position",
        "kind": "write",
        "summary": "写入或更新持仓",
        "params": {"code": "str", "buy_price": "number", "shares": "number", "name": "str?"},
    },
    {
        "name": "remove_position",
        "kind": "write",
        "summary": "删除持仓（代码或名称）",
        "params": {"code": "str"},
    },
    {
        "name": "apply_strategy_patch",
        "kind": "write",
        "summary": "执行已确认的 strategy_patch",
        "params": {"patch": "object"},
    },
    {
        "name": "apply_memory_notes",
        "kind": "write",
        "summary": "确认写入对话沉淀",
        "params": {"patch": "object", "source_question": "str?"},
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
        "summary": "新建或覆盖知识库 Markdown",
        "params": {"path": "str", "content": "str", "create": "bool?"},
    },
    {
        "name": "upload_kb_document",
        "kind": "write",
        "summary": "上传文件抽成 Markdown 入库",
        "params": {"filename": "str", "data_b64": "str?", "overwrite": "bool?"},
    },
    {
        "name": "delete_kb_document",
        "kind": "write",
        "summary": "删除知识库 Markdown",
        "params": {"path": "str"},
    },
    {
        "name": "preview_kb_chunks",
        "kind": "read",
        "summary": "预览切块结果",
        "params": {"path": "str?", "content": "str?"},
    },
    {
        "name": "kb_overview",
        "kind": "read",
        "summary": "知识库与索引概览",
        "params": {},
    },
    {
        "name": "reindex_knowledge",
        "kind": "write",
        "summary": "重建知识库向量索引",
        "params": {},
    },
]


def list_capabilities() -> list[dict[str, Any]]:
    return list(CAPABILITY_META)


def invoke(name: str, **kwargs: Any) -> Any:
    fn = CALLABLES.get(name)
    if not fn:
        raise KeyError(f"unknown_capability:{name}")
    return fn(**kwargs)
