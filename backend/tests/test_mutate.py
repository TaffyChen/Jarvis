from __future__ import annotations

from app.capabilities.mutate import (
    add_code,
    apply_strategy_patch,
    remove_position,
    resolve_position_code,
    upsert_position,
)
from app.infra.storage import read_json


def test_upsert_position_also_adds_universe(isolated_data_dir):
    result = upsert_position("000333", 58.8, 100, name="美的集团")
    assert result["ok"] is True
    assert result["code"] == "sz000333"
    assert result["need_quotes"] is True

    positions = read_json("positions.json", {})
    assert positions["sz000333"]["buyPrice"] == 58.8
    assert positions["sz000333"]["shares"] == 100.0
    assert positions["sz000333"]["name"] == "美的集团"

    codes = read_json("stock_codes.json", [])
    assert "sz000333" in codes


def test_remove_position_by_name(isolated_data_dir):
    upsert_position("000333", 58.8, 100, name="美的集团")
    assert resolve_position_code("美的集团") == "sz000333"

    result = remove_position("美的集团")
    assert result == {
        "ok": True,
        "code": "sz000333",
        "name": "美的集团",
        "removed": True,
    }
    assert read_json("positions.json", {}) == {}


def test_apply_strategy_patch_remove_with_name_payload(isolated_data_dir):
    upsert_position("000333", 58.8, 100, name="美的集团")
    patch = {
        "type": "strategy_patch",
        "summary": "删除美的",
        "patches": [
            {
                "target": "positions",
                "action": "remove",
                "payload": {"name": "美的集团"},
            }
        ],
    }
    result = apply_strategy_patch(patch)
    assert result["success"] is True
    assert any(
        item["target"] == "positions"
        and item["action"] == "remove"
        and item["code"] == "sz000333"
        for item in result["items"]
    )
    assert read_json("positions.json", {}) == {}


def test_apply_strategy_patch_positions_upsert_missing_fields(isolated_data_dir):
    add_code("000333", name="美的集团")
    patch = {
        "type": "strategy_patch",
        "summary": "缺字段",
        "patches": [{"target": "positions", "code": "000333", "action": "upsert", "payload": {}}],
    }
    result = apply_strategy_patch(patch)
    assert result["success"] is True
    assert result["items"][0]["action"] == "skipped_missing_fields"
