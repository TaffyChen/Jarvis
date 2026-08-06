"""
Jarvis services —— 多入口共用的应用服务层
=======================================
业务只在这里实现一次。分层：api / mcp / agents → services → domain / infrastructure。

```python
from app.services import invoke, list_capabilities, add_code
```
"""
from __future__ import annotations

from app.services.analyses import get_analysis, list_analyses, upsert_analysis
from app.services.auth import login, logout, me
from app.services.codes import add_code, add_codes, remove_codes, search_codes
from app.services.conversations import append_conversation, list_conversations
from app.services.journal import add_journal, get_journal, list_journal
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
from app.services.memory import apply_memory_notes, list_memories, search_memories
from app.services.patches import apply_strategy_patch
from app.services.positions import (
    get_positions,
    list_positions_map,
    remove_position,
    resolve_position_code,
    save_positions_map,
    upsert_position,
)
from app.services.quotes import (
    get_market_overview,
    get_quote,
    get_score,
    health_snapshot,
    indices_snapshot,
    klines_snapshot,
    quotes_snapshot,
    refresh_klines,
    refresh_quotes,
)
from app.services.rag import retrieve_for_dialog, retrieve_knowledge
from app.services.screen import auction_top, screen_top, sector_flow


def list_capabilities():
    from app.services.registry import list_capabilities as _list

    return _list()


def invoke(name: str, **kwargs):
    from app.services.registry import invoke as _invoke

    return _invoke(name, **kwargs)


__all__ = [
    "search_knowledge",
    "retrieve_knowledge",
    "retrieve_for_dialog",
    "search_memories",
    "search_codes",
    "get_quote",
    "get_score",
    "get_analysis",
    "get_positions",
    "get_market_overview",
    "get_journal",
    "add_code",
    "add_codes",
    "remove_codes",
    "upsert_position",
    "remove_position",
    "resolve_position_code",
    "apply_strategy_patch",
    "apply_memory_notes",
    "list_kb_documents",
    "get_kb_document",
    "save_kb_document",
    "upload_kb_document",
    "delete_kb_document",
    "preview_kb_chunks",
    "kb_overview",
    "reindex_knowledge",
    "list_capabilities",
    "invoke",
    "login",
    "logout",
    "me",
    "list_analyses",
    "upsert_analysis",
    "list_positions_map",
    "save_positions_map",
    "list_journal",
    "add_journal",
    "list_conversations",
    "append_conversation",
    "list_memories",
    "health_snapshot",
    "quotes_snapshot",
    "indices_snapshot",
    "klines_snapshot",
    "refresh_quotes",
    "refresh_klines",
    "screen_top",
    "auction_top",
    "sector_flow",
]
