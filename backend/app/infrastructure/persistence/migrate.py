"""遗留 JSON / kv_docs 迁入业务表。"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.infrastructure.persistence import storage
from app.infrastructure.persistence.analyses_store import save_analyses
from app.infrastructure.persistence.conversations_store import save_conversations
from app.infrastructure.persistence.memory_store import save_memories
from app.infrastructure.persistence.positions_store import save_positions
from app.infrastructure.persistence.proposals_store import save_proposals
from app.infrastructure.persistence.schema import ensure_schema
from app.infrastructure.persistence.watch_store import save_watch_codes

_DOC_FILES = (
    "stock_codes.json",
    "positions.json",
    "analyses.json",
    "memory_notes.json",
    "strategy_proposals.json",
    "conversations.json",
)


def migrate_legacy() -> dict[str, Any]:
    if not storage.mysql_enabled():
        return {"skipped": "mysql_disabled"}
    ensure_schema()
    stats: dict[str, int] = {}

    codes = _merge_list(_table_count("watch_codes"), "stock_codes.json", [])
    if codes is not None:
        save_watch_codes([c for c in codes if isinstance(c, str)])
        stats["watch_codes"] = len(codes)

    positions = _merge_dict(_table_count("positions"), "positions.json", {})
    if positions is not None:
        save_positions(positions)
        stats["positions"] = len(positions)

    analyses = _merge_dict(_table_count("analyses"), "analyses.json", {})
    if analyses is not None:
        save_analyses(analyses)
        stats["analyses"] = len(analyses)

    memories = _merge_list(_table_count("memory_notes"), "memory_notes.json", [])
    if memories is not None:
        save_memories(memories)
        stats["memory_notes"] = len(memories)

    proposals = _merge_list(_table_count("strategy_proposals"), "strategy_proposals.json", [])
    if proposals is not None:
        save_proposals(proposals)
        stats["strategy_proposals"] = len(proposals)

    conv = _merge_list(_table_count("conversations"), "conversations.json", [])
    if conv is not None:
        save_conversations(conv)
        stats["conversations"] = len(conv)

    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM kv_docs WHERE doc_name IN ({','.join(['%s'] * len(_DOC_FILES))})",
            _DOC_FILES,
        )
    cleared = []
    for name in _DOC_FILES:
        path = settings.data_dir / name
        if path.exists():
            path.unlink()
            cleared.append(name)
    return {"migrated": stats, "clearedJson": cleared}


def _table_count(table: str) -> int:
    conn = storage.mysql_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
        row = cur.fetchone() or {}
    return int(row.get("c") or 0)


def _merge_list(table_count: int, doc_name: str, default):
    if table_count > 0:
        return None
    legacy = _legacy_doc(doc_name, default)
    return legacy if isinstance(legacy, list) and legacy else ([] if isinstance(legacy, list) else None)


def _merge_dict(table_count: int, doc_name: str, default):
    if table_count > 0:
        return None
    legacy = _legacy_doc(doc_name, default)
    return legacy if isinstance(legacy, dict) and legacy else ({} if isinstance(legacy, dict) else None)


def _legacy_doc(name: str, default: Any):
    try:
        val = storage._mysql_read(name)
        if val is not None:
            return val
    except Exception:
        pass
    return storage._file_read(name, default)