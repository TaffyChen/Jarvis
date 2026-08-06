from __future__ import annotations

from app.services.screen import enrich_screen_row


def test_enrich_adds_discipline_and_volume_tags(isolated_data_dir):
    discipline = {
        "buyAllowed": False,
        "hint": "情绪退潮：只卖不买",
        "text": "0红灯 | 有效≤3成（情绪退潮）",
    }
    row = enrich_screen_row(
        {
            "code": "sz300750",
            "name": "宁德",
            "price": 100,
            "changePct": 0.2,
            "liangbi": 2.4,
            "aboveMA20": True,
            "ma20": 95,
            "signals": ["低PE(20)"],
            "score": 80,
        },
        discipline=discipline,
        positions=set(),
        watch=set(),
        kind="screen",
    )
    assert row["score"] == 80
    assert row["flags"]["buyDiscouraged"] is True
    assert "放量滞涨" in row["signals"]
    assert "纪律:不宜新开" in row["signals"]


def test_enrich_auction_vs_open_and_position(isolated_data_dir):
    discipline = {"buyAllowed": True}
    row = enrich_screen_row(
        {
            "code": "sz000636",
            "name": "风华",
            "price": 9.5,
            "open": 10.0,
            "changePct": 4.0,
            "liangbi": 1.2,
            "signals": ["高开+4.0%"],
            "score": 55,
        },
        discipline=discipline,
        positions={"sz000636"},
        watch=set(),
        kind="auction",
    )
    assert row["flags"]["inPosition"] is True
    assert row["flags"]["brokeOpen"] is True
    assert row["vsOpenPct"] < 0
    assert "已持仓" in row["signals"]
    assert any("破开盘" in s for s in row["signals"])
