from __future__ import annotations

from app.infrastructure.persistence.journal_store import add_journal_entry, list_journal_entries
from app.services.journal import get_journal
from app.services.patches import apply_strategy_patch


def test_journal_json_fallback_roundtrip(isolated_data_dir):
    add_journal_entry(
        {
            "ts": "2026-08-05T08:00:12.100Z",
            "code": "sz000636",
            "name": "风华高科",
            "level": "warning",
            "msg": "盈利达止盈线",
            "action": "强制兑现部分",
            "note": "建仓一半",
            "lamps": 1,
        }
    )
    rows = list_journal_entries()
    assert rows[0]["code"] == "sz000636"
    assert rows[0]["note"] == "建仓一半"
    assert get_journal(1)[0]["name"] == "风华高科"


def test_journal_search_by_keyword_level_and_code(isolated_data_dir):
    add_journal_entry(
        {
            "ts": "2026-08-05T08:00:12.100Z",
            "code": "sz000636",
            "name": "风华高科",
            "level": "warning",
            "msg": "盈利达止盈线",
            "action": "强制兑现部分",
            "note": "建仓一半",
            "lamps": 1,
        }
    )
    add_journal_entry(
        {
            "ts": "2026-08-05T09:10:00.000Z",
            "code": "sz300750",
            "name": "宁德时代",
            "level": "danger",
            "msg": "跌破冰点",
            "action": "考虑止损",
            "note": "等明天竞价",
            "lamps": 4,
        }
    )
    assert [r["name"] for r in list_journal_entries(q="风华")] == ["风华高科"]
    assert [r["name"] for r in list_journal_entries(q="000636")] == ["风华高科"]
    assert [r["name"] for r in list_journal_entries(level="danger")] == ["宁德时代"]
    assert [r["name"] for r in list_journal_entries(code="000636")] == ["风华高科"]
    assert get_journal(limit=5, q="止损")[0]["code"] == "sz300750"


def test_strategy_patch_writes_journal(isolated_data_dir):
    result = apply_strategy_patch(
        {
            "type": "strategy_patch",
            "summary": "记下操作",
            "patches": [{"target": "journal", "action": "add_note", "payload": {"note": "已减半仓"}}],
        }
    )
    assert result["success"] is True
    rows = list_journal_entries()
    assert rows
    assert rows[0]["note"] == "已减半仓"
    assert rows[0]["name"] == "Jarvis"
