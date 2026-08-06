from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.persistence import review_store
from app.services.review import generate_brief, get_brief_day, get_brief_version, list_brief_days


def test_brief_versions_append_not_overwrite(isolated_data_dir):
    v1 = review_store.create_version(
        brief_date="2026-08-05",
        snapshot={"date": "2026-08-05", "n": 1},
        report_md="**一句话定性：** 上午换防\n\n## 验证窗口\n- a",
        model="t1",
    )
    v2 = review_store.create_version(
        brief_date="2026-08-05",
        snapshot={"date": "2026-08-05", "n": 2},
        report_md="**一句话定性：** 下午退潮\n\n## 验证窗口\n- b",
        model="t2",
    )
    assert v1["id"] != v2["id"]
    day = get_brief_day("2026-08-05")
    assert day is not None
    assert len(day["versions"]) == 2
    assert list_brief_days()[0]["versionCount"] == 2
    assert "下午退潮" in (list_brief_days()[0]["headline"] or "")

    review_store.add_comment(v1["id"], "上午版已据此减仓")
    got = get_brief_version(v1["id"])
    assert len(got["comments"]) == 1
    assert get_brief_version(v2["id"])["comments"] == []

    marked = review_store.mark_final(v2["id"])
    assert marked["isFinal"] is True
    assert get_brief_version(v1["id"])["isFinal"] is False
    assert list_brief_days()[0]["hasFinal"] is True


def test_generate_appends_and_regen_keeps_base(isolated_data_dir, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "llm_api_key", "missing", raising=False)
    first = asyncio.run(generate_brief(refresh_snapshot=True, brief_date="2026-08-06"))
    assert first["success"] is True
    vid = first["version"]["id"]
    review_store.add_comment(vid, "小金属一日游")
    second = asyncio.run(
        generate_brief(refresh_snapshot=False, base_version_id=vid)
    )
    assert second["success"] is True
    assert second["version"]["id"] != vid
    assert get_brief_version(vid) is not None
    assert any("一日游" in c.get("text", "") for c in get_brief_version(vid)["comments"])
    assert second["version"]["comments"] == []
    assert len(get_brief_day("2026-08-06")["versions"]) == 2


def test_regen_without_base_raises(isolated_data_dir, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "llm_api_key", "missing", raising=False)
    with pytest.raises(ValueError, match="基准"):
        asyncio.run(generate_brief(refresh_snapshot=False, base_version_id=99999))
