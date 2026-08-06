"""盘后选股 / 竞价 / 板块资金。

打分仍在 market 层；本层叠加纪律滤镜与知识库对齐的信号标签（不改排序核）。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.infrastructure.market.service import market
from app.infrastructure.persistence import positions_store, watch_store

_SENTIMENT_UP_PCT = 0.4
_SENTIMENT_UP_COUNT = 1500
_LAMP_CAPS = {0: 0.8, 1: 0.5, 2: 0.3, 3: 0.1}
_SENTIMENT_CAP = 0.3


async def screen_top() -> dict[str, Any]:
    raw = await market.screen_top()
    return _enrich_payload(raw, kind="screen")


async def auction_top() -> dict[str, Any]:
    raw = await market.auction_top()
    return _enrich_payload(raw, kind="auction")


async def sector_flow() -> dict[str, Any]:
    if not market.sector_flow_cache.get("list"):
        await market.fetch_all_quotes()
    return market.sector_flow_cache


def build_discipline_context() -> dict[str, Any]:
    """与盘面简报 / 前端有效仓位同口径的软门禁（用于榜单提示，不改打分）。"""
    mb = market.market_breadth or {}
    breadth = market.breadth or {}
    use_mb = mb if (mb.get("total") or 0) > 0 else breadth
    up = int(use_mb.get("up") or 0)
    down = int(use_mb.get("down") or 0)
    total = int(use_mb.get("total") or 0) or (up + down)
    up_pct = (up / total) if total else None

    retreat = False
    if total > 0 and up_pct is not None:
        retreat = up_pct < _SENTIMENT_UP_PCT or (
            (mb.get("total") or 0) > 0 and up < _SENTIMENT_UP_COUNT
        )

    lamps = _lamps_lite()
    red = sum(1 for x in lamps if x.get("red"))
    lamp_cap = 0.0 if red >= 4 else _LAMP_CAPS.get(red, 0.8)
    sentiment_cap = _SENTIMENT_CAP if retreat else None
    effective = min(lamp_cap, sentiment_cap) if sentiment_cap is not None else lamp_cap
    buy_allowed = effective > 0 and not retreat

    if effective <= 0:
        text = f"{red}红灯 | 仓位归零"
        hint = "今日不宜新开（仓位归零）"
    elif retreat:
        text = f"{red}红灯 | 有效≤{int(round(effective * 10))}成（情绪退潮）"
        hint = "情绪退潮：只卖不买，榜单仅作观察"
    else:
        text = f"{red}红灯 | 仓位上限{int(round(lamp_cap * 10))}成"
        hint = ""

    return {
        "sentimentRetreat": retreat,
        "lampRed": red,
        "lampCap": lamp_cap,
        "sentimentCap": sentiment_cap,
        "effectiveCap": effective,
        "buyAllowed": buy_allowed,
        "text": text,
        "hint": hint,
        "breadth": {"up": up, "down": down, "total": total, "upPct": round(up_pct * 100, 1) if up_pct is not None else None},
    }


def enrich_screen_row(
    row: dict[str, Any],
    *,
    discipline: dict[str, Any],
    positions: set[str],
    watch: set[str],
    kind: str,
) -> dict[str, Any]:
    """给单行挂 flags + 对齐知识库的信号（不改 score）。"""
    out = dict(row)
    code = str(out.get("code") or "")
    signals = list(out.get("signals") or [])
    lb = float(out.get("liangbi") or 0)
    chg = float(out.get("changePct") or 0)

    in_pos = code in positions
    in_watch = code in watch
    below_ma20 = None
    if "aboveMA20" in out and out.get("ma20"):
        below_ma20 = not bool(out.get("aboveMA20"))
    else:
        k = market.kline_cache.get(code) or {}
        q_price = float(out.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if ma20 > 0 and q_price > 0:
            below_ma20 = q_price < ma20

    # 量价：放量不涨价 / 放量下跌（量价与主力行为）
    if lb >= 2.5 and chg <= -3:
        _add_signal(signals, "放量下跌警惕")
    elif lb >= 2 and chg < 1:
        _add_signal(signals, "放量滞涨")

    # 竞价后：相对开盘价（开盘三十分钟锚点，粗粒度）
    broke_open = None
    if kind == "auction":
        open_p = float(out.get("open") or 0)
        price = float(out.get("price") or 0)
        if open_p > 0 and price > 0:
            vs = (price - open_p) / open_p * 100
            out["vsOpenPct"] = round(vs, 2)
            if vs < -0.3:
                broke_open = True
                _add_signal(signals, f"现价破开盘{vs:.1f}%")
            elif vs > 0.3:
                broke_open = False
                _add_signal(signals, f"站上开盘+{vs:.1f}%")
            else:
                broke_open = False
                _add_signal(signals, "贴着开盘价")

    if in_pos:
        _add_signal(signals, "已持仓", front=True)
    if in_pos and below_ma20:
        _add_signal(signals, "持仓破20日线", front=True)
    elif below_ma20 and kind == "screen":
        _add_signal(signals, "破20日线")

    buy_discouraged = not bool(discipline.get("buyAllowed"))
    if buy_discouraged:
        _add_signal(signals, "纪律:不宜新开")

    out["flags"] = {
        "inPosition": in_pos,
        "inWatch": in_watch,
        "belowMA20": below_ma20,
        "brokeOpen": broke_open,
        "buyDiscouraged": buy_discouraged,
    }
    out["signals"] = signals[:10]
    return out


def _enrich_payload(raw: dict[str, Any], *, kind: str) -> dict[str, Any]:
    discipline = build_discipline_context()
    positions = set((positions_store.load_positions() or {}).keys())
    watch = set(watch_store.load_watch_codes() or [])
    results = [
        enrich_screen_row(r, discipline=discipline, positions=positions, watch=watch, kind=kind)
        for r in (raw.get("results") or [])
        if isinstance(r, dict)
    ]
    out = dict(raw)
    out["results"] = results
    out["discipline"] = discipline
    out["kind"] = kind
    return out


def _add_signal(signals: list[str], text: str, *, front: bool = False) -> None:
    if text in signals:
        return
    if front:
        signals.insert(0, text)
    else:
        signals.append(text)


def _lamps_lite() -> list[dict[str, Any]]:
    lamps: list[dict[str, Any]] = []
    turns: list[float] = []
    for code, q in (market.quote_cache or {}).items():
        if str(code).startswith(("sh5", "sz1")):
            continue
        t = float(q.get("turnover") or q.get("turnOver") or 0)
        if t > 0:
            turns.append(t)
    avg_turn = sum(turns) / len(turns) if turns else 0.0
    lamps.append({"name": "换手拥挤", "red": avg_turn > 10})
    lamps.append({"name": "杠杆5连降", "red": False})
    today = date.today()
    m, d = today.month, today.day
    earn = (m == 1 and 17 <= d <= 31) or (m == 7 and 1 <= d <= 15)
    lamps.append({"name": "业绩验证期", "red": earn})
    ov = market.overseas or {}
    spx = float(ov.get("changePct") or 0) if ov else 0.0
    nas = market.quote_cache.get("sz159659") or {}
    nas_chg = float(nas.get("changePct") or 0)
    overseas_red = (bool(ov) and spx <= -1.5) or (bool(nas.get("price")) and nas_chg <= -2.0)
    lamps.append({"name": "海外隔夜大跌", "red": overseas_red})
    positions = positions_store.load_positions() or {}
    below = with_ma = 0
    for code in positions:
        q = market.quote_cache.get(code) or {}
        k = market.kline_cache.get(code) or {}
        price = float(q.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if price > 0 and ma20 > 0:
            with_ma += 1
            if price < ma20:
                below += 1
    pct = (below / with_ma) if with_ma else 0.0
    lamps.append({"name": "持仓破20日线", "red": with_ma > 0 and pct > 0.5})
    return lamps
