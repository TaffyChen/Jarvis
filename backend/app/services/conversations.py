"""站内对话流水 / 会话。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence import conversations_store as store


def list_conversations() -> list[dict[str, Any]]:
    return store.load_conversations()


def append_conversation(row: dict[str, Any], session_id: int | None = None) -> dict[str, Any]:
    return store.append_turn(row, session_id=session_id)


def create_chat_session(title: str = "") -> dict[str, Any]:
    return store.create_session(title)


def list_chat_sessions(limit: int = 40) -> list[dict[str, Any]]:
    return store.list_sessions(limit=limit)


def get_chat_session(session_id: int) -> dict[str, Any] | None:
    return store.get_session(session_id)
