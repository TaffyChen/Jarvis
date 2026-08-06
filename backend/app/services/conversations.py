"""站内对话流水。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence.conversations_store import load_conversations, save_conversations


def list_conversations() -> list[dict[str, Any]]:
    return load_conversations()


def append_conversation(row: dict[str, Any]) -> None:
    conv = load_conversations()
    conv.insert(0, row)
    save_conversations(conv[:100])
