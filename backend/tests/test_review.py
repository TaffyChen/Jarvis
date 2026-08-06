from __future__ import annotations

from app.services.review import build_daily_review_snapshot, _fallback_markdown


def test_daily_review_snapshot_shape(isolated_data_dir):
    snap = build_daily_review_snapshot()
    assert snap["date"]
    assert "positionCap" in snap
    assert "effectiveCap" in snap["positionCap"]
    assert "market" in snap
    assert "sectors" in snap
    assert isinstance(snap["dataGaps"], list)
    md = _fallback_markdown(snap)
    assert "验证窗口" in md
    assert "不构成投资建议" in md
