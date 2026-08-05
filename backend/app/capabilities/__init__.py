"""
Jarvis Capabilities —— 多 Agent 共用的能力层
==========================================
业务只在这里实现一次。分层关系见 `docs/ARCHITECTURE.md`。

调用方（适配，不写业务）：
- LangGraph tools → query
- HTTP `GET/POST /api/jarvis/capabilities*`
- MCP：`python -m app.mcp` / `bash scripts/mcp.sh`

```python
from app.capabilities import invoke, list_capabilities, add_code
list_capabilities()
invoke("get_quote", code="sz300408")
add_code("600693", name="东百集团")
```
"""
from __future__ import annotations

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
from app.capabilities.rag import retrieve_for_dialog, retrieve_knowledge
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


def list_capabilities():
    from app.capabilities.registry import list_capabilities as _list

    return _list()


def invoke(name: str, **kwargs):
    from app.capabilities.registry import invoke as _invoke

    return _invoke(name, **kwargs)


__all__ = [
    "search_knowledge",
    "retrieve_knowledge",
    "retrieve_for_dialog",
    "search_memory",
    "search_codes",
    "get_quote",
    "get_score",
    "get_analysis",
    "get_positions",
    "get_market_overview",
    "get_journal",
    "add_code",
    "upsert_position",
    "remove_position",
    "apply_strategy_patch",
    "apply_memory_notes",
    "list_kb_documents",
    "get_kb_document",
    "save_kb_document",
    "delete_kb_document",
    "preview_kb_chunks",
    "kb_overview",
    "reindex_knowledge",
    "list_capabilities",
    "invoke",
]
