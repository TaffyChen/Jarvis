"""纪律日记。"""
from __future__ import annotations

from typing import Any

from app.infrastructure.persistence.journal_store import add_journal_entry, list_journal_entries


def list_journal(
    limit: int | None = None,
    *,
    q: str | None = None,
    level: str | None = None,
    code: str | None = None,
) -> list[dict[str, Any]]:
    n = None if limit is None else max(1, min(int(limit), 500))
    return list_journal_entries(limit=n, q=q, level=level, code=code)


def add_journal(entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if isinstance(entry, dict):
        add_journal_entry(entry)
    return list_journal_entries()


def get_journal(
    limit: int = 5,
    q: str = "",
    level: str = "",
    code: str = "",
) -> list[dict[str, Any]]:
    n = max(1, min(int(limit or 5), 20))
    return list_journal_entries(limit=n, q=q or None, level=level or None, code=code or None)
