"""
Jarvis MCP Server（官方 mcp SDK · FastMCP）
==========================================
把 services 暴露给 Cursor / Claude Desktop 等 MCP 客户端。

启动：
  cd backend && PYTHONPATH=. .venv/bin/python -m app.mcp
  或：bash scripts/mcp.sh

要求：Python >= 3.10（当前 backend/.venv 使用 3.12）
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.services.registry import CAPABILITY_META, invoke

mcp = FastMCP(
    "jarvis",
    instructions=(
        "Jarvis 个人交易参谋能力层。"
        "只读工具可随时调用；写入工具（add_code / upsert_position / apply_*）会改本地数据，请谨慎确认。"
    ),
)


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, indent=2)


@mcp.resource("jarvis://capabilities")
def resource_capabilities() -> str:
    """能力清单（只读发现）。"""
    return _json(CAPABILITY_META)


@mcp.tool()
def list_jarvis_capabilities() -> str:
    """列出 Jarvis 全部共用能力及是否建议人工确认。"""
    return _json(CAPABILITY_META)


@mcp.tool()
def search_knowledge(query: str, top_k: int = 5) -> str:
    """检索本地纪律知识库与 analyses 索引。"""
    return _json(invoke("search_knowledge", query=query, top_k=top_k))


@mcp.tool()
def search_memory(query: str, top_k: int = 5) -> str:
    """检索对话沉淀认知卡片。"""
    return _json(invoke("search_memory", query=query, top_k=top_k))


@mcp.tool()
def get_quote(code: str) -> str:
    """查询单只标的实时行情缓存。code 如 600693 或 sz300408。"""
    return _json(invoke("get_quote", code=code))


@mcp.tool()
def get_score(code: str) -> str:
    """计算综合评分与关键因子。"""
    return _json(invoke("get_score", code=code))


@mcp.tool()
def get_analysis(code: str) -> str:
    """读取利空复核与定性分析。"""
    return _json(invoke("get_analysis", code=code))


@mcp.tool()
def get_positions() -> str:
    """列出当前持仓及现价。"""
    return _json(invoke("get_positions"))


@mcp.tool()
def get_market_overview() -> str:
    """市场广度、海外、涨停摘要。"""
    return _json(invoke("get_market_overview"))


@mcp.tool()
def get_journal(limit: int = 5, q: str = "", level: str = "", code: str = "") -> str:
    """纪律日记。可按关键词、级别、代码检索。"""
    return _json(invoke("get_journal", limit=limit, q=q, level=level, code=code))


@mcp.tool()
def add_code(code: str, name: str = "", type: str = "", notes: str = "") -> str:
    """【写入】将标的加入观察池。会改本地数据，请确认后再调。"""
    kwargs: dict[str, Any] = {"code": code}
    if name:
        kwargs["name"] = name
    if type:
        kwargs["type"] = type
    if notes:
        kwargs["notes"] = notes
    return _json(invoke("add_code", **kwargs))


@mcp.tool()
def upsert_position(code: str, buy_price: float, shares: float, name: str = "") -> str:
    """【写入】写入/更新持仓。会改本地数据，请确认后再调。"""
    kwargs: dict[str, Any] = {"code": code, "buy_price": buy_price, "shares": shares}
    if name:
        kwargs["name"] = name
    return _json(invoke("upsert_position", **kwargs))


@mcp.tool()
def remove_position(code: str) -> str:
    """【写入】删除持仓（代码或名称均可）。不移出观察池。请确认后再调。"""
    return _json(invoke("remove_position", code=code))


@mcp.tool()
def apply_strategy_patch(patch_json: str) -> str:
    """【写入】执行 strategy_patch JSON 字符串（HITL 确认后的内容）。"""
    try:
        patch = json.loads(patch_json)
    except Exception as e:
        return _json({"ok": False, "error": f"invalid_json:{e}"})
    return _json(invoke("apply_strategy_patch", patch=patch))


@mcp.tool()
def apply_memory_notes(patch_json: str, source_question: str = "") -> str:
    """【写入】执行 memory_patch JSON 字符串。"""
    try:
        patch = json.loads(patch_json)
    except Exception as e:
        return _json({"ok": False, "error": f"invalid_json:{e}"})
    return _json(invoke("apply_memory_notes", patch=patch, source_question=source_question))


@mcp.tool()
def list_kb_documents() -> str:
    """列出 knowledge/*.md 文档。"""
    return _json(invoke("list_kb_documents"))


@mcp.tool()
def get_kb_document(path: str) -> str:
    """读取一篇知识库 Markdown，path 如 三原则两防线.md。"""
    return _json(invoke("get_kb_document", path=path))


@mcp.tool()
def save_kb_document(path: str, content: str, create: bool = False) -> str:
    """【写入】新建或覆盖 knowledge 下的 Markdown。改完后请调用 reindex_knowledge。"""
    return _json(invoke("save_kb_document", path=path, content=content, create=create))


@mcp.tool()
def upload_kb_document(
    filename: str = "",
    content_base64: str = "",
    source_path: str = "",
    overwrite: bool = False,
) -> str:
    """【写入】上传本地文件到知识库。支持 md/txt/pdf/docx/xlsx/html/csv，抽成 Markdown。优先 source_path，或传 filename+content_base64。"""
    kwargs: dict[str, Any] = {"overwrite": overwrite}
    if filename:
        kwargs["filename"] = filename
    if content_base64:
        kwargs["content_base64"] = content_base64
    if source_path:
        kwargs["source_path"] = source_path
    return _json(invoke("upload_kb_document", **kwargs))


@mcp.tool()
def delete_kb_document(path: str) -> str:
    """【写入】删除 knowledge 下的 Markdown。"""
    return _json(invoke("delete_kb_document", path=path))


@mcp.tool()
def preview_kb_chunks(path: str = "", content: str = "") -> str:
    """预览切块（不写索引）。给 path 或直接给 content。"""
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if content:
        kwargs["content"] = content
    return _json(invoke("preview_kb_chunks", **kwargs))


@mcp.tool()
def kb_overview() -> str:
    """知识库状态：向量后端、embedding、文档列表、是否需重建。"""
    return _json(invoke("kb_overview"))


@mcp.tool()
def reindex_knowledge() -> str:
    """【写入】重建知识库向量索引（local JSON 或 Milvus）。"""
    return _json(invoke("reindex_knowledge"))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
