"""五灯仓位：全市场硬/软灯 → 总仓上限（与前端 signals.js v4.1 同口径）。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.infrastructure.market.service import market

# 与 frontend/src/utils/strategy.js 保持一致
OVERSEAS_SPX_RED = -1.5
OVERSEAS_NDX_RED = -2.0
INDEX_BREAK_CODES = ("sh000300", "sz399006")
INDEX_BREAK_CONFIRM_DAYS = 3
ECO_YEST_LOSS_RED = 3
ECO_DT_RED = 10
ECO_MAX_DAYS_COLD = 2


def is_earnings_window(today: date | None = None) -> bool:
    d = today or date.today()
    return (d.month == 1 and 17 <= d.day <= 31) or (d.month == 7 and 1 <= d.day <= 15)


def red_count_to_cap(red_count: int, hard_count: int, soft_count: int) -> float:
    cap = 0.8
    if red_count >= 4:
        cap = 0.0
    elif red_count >= 3:
        cap = 0.1
    elif red_count >= 2:
        cap = 0.3
    elif red_count >= 1:
        cap = 0.5
    if hard_count >= 2:
        cap = min(cap, 0.1)
    if hard_count <= 0 and soft_count > 0:
        cap = 0.3
    return cap


def level_for_cap(cap: float) -> str:
    if cap <= 0.1:
        return "danger"
    if cap <= 0.5:
        return "warning"
    return "safe"


def lamp_cap_from_lamps(lamps: list[dict[str, Any]]) -> dict[str, Any]:
    hard = 0
    soft = 0
    lit = 0
    for lamp in lamps:
        if not lamp.get("red"):
            continue
        lit += 1
        if lamp.get("kind") == "soft":
            soft += 1
        else:
            hard += 1
    cap = red_count_to_cap(lit, hard, soft)
    return {
        "redCount": lit,
        "hardCount": hard,
        "softCount": soft,
        "hardScore": hard,
        "softScore": soft,
        "riskScore": lit,
        "lampCap": cap,
        "level": level_for_cap(cap),
        "text": _cap_label(lit, cap),
    }


def _cap_label(lit: int, cap: float) -> str:
    if cap <= 0:
        return f"{lit}盏亮 | 仓位归零"
    return f"{lit}盏亮 | 仓位上限{int(round(cap * 10))}成"


def _ma60_at(closes: list[float], idx: int) -> float:
    if idx < 59 or idx >= len(closes):
        return 0.0
    window = closes[idx - 59 : idx + 1]
    if len(window) < 60:
        return 0.0
    return sum(window) / 60.0


def _consecutive_below_ma60(k: dict[str, Any], need: int = INDEX_BREAK_CONFIRM_DAYS) -> tuple[bool, int]:
    bars = k.get("klines") or []
    if len(bars) < 60:
        return False, 0
    closes = [float(b.get("close") or 0) for b in bars]
    n = 0
    for i in range(len(closes) - 1, 58, -1):
        ma = _ma60_at(closes, i)
        close = closes[i]
        if not (ma > 0 and close > 0):
            break
        if close < ma:
            n += 1
        else:
            break
    return n >= need, n


def compute_lamps(*, lever_red: bool = False) -> list[dict[str, Any]]:
    """全市场五灯；杠杆灯默认熄灭。"""
    lamps: list[dict[str, Any]] = []
    lu = getattr(market, "limit_up_stats", None) or {}

    # 1 指数破位：沪深300 / 创业板 连续3日收盘破 MA60
    name_map = {"sh000300": "沪深300", "sz399006": "创业板"}
    broken: list[str] = []
    known = 0
    for code in INDEX_BREAK_CODES:
        k = market.kline_cache.get(code) or {}
        if (k.get("klines") or []) and len(k["klines"]) >= 60:
            known += 1
            ok, days = _consecutive_below_ma60(k)
            if ok:
                broken.append(f"{name_map.get(code, code)}{days}日")
    break_red = len(broken) > 0
    lamps.append(
        {
            "id": "index_break",
            "name": "指数破位",
            "red": break_red,
            "kind": "hard",
            "weight": 1.0,
            "detail": (
                f"{'、'.join(broken)}破MA60"
                if broken
                else (f"沪深300/创业未连破MA60（样本{known}）" if known else "指数均线样本不足（等K线刷新）")
            ),
        }
    )

    # 2 海外冲击
    ov = market.overseas or {}
    spx = ov.get("changePct")
    nas = market.quote_cache.get("sz159659") or {}
    nas_idx = ov.get("nasdaq") if isinstance(ov.get("nasdaq"), dict) else {}
    nas_chg = None
    if nas.get("price") and nas.get("changePct") is not None:
        nas_chg = float(nas.get("changePct") or 0)
    elif nas_idx.get("changePct") is not None:
        nas_chg = float(nas_idx.get("changePct") or 0)
    overseas_red = (spx is not None and float(spx) <= OVERSEAS_SPX_RED) or (
        nas_chg is not None and nas_chg <= OVERSEAS_NDX_RED
    )
    od = []
    if spx is not None:
        od.append(f"标普{float(spx):.2f}%")
    if nas_chg is not None:
        od.append(f"纳指{nas_chg:.2f}%")
    lamps.append(
        {
            "id": "overseas",
            "name": "海外冲击",
            "red": overseas_red,
            "kind": "hard",
            "weight": 1.0,
            "detail": " / ".join(od) if od else "海外数据不足",
        }
    )

    # 3 生态恶化
    zt = int(lu.get("zt") or 0)
    dt = int(lu.get("dt") or 0)
    max_days = int(lu.get("maxDays") or 0)
    yest_loss = int(lu.get("yestLoss") if lu.get("yestLoss") is not None else (lu.get("bigDrawdown") or 0))
    eco_reasons: list[str] = []
    if yest_loss >= ECO_YEST_LOSS_RED:
        eco_reasons.append(f"昨涨停今亏{yest_loss}家")
    if dt >= ECO_DT_RED:
        eco_reasons.append(f"跌停{dt}家")
    # maxDays=0 常为样本空；需涨停样本够且高度可读
    if zt >= 20 and max_days >= 1 and max_days <= ECO_MAX_DAYS_COLD:
        eco_reasons.append(f"连板高度{max_days}≤{ECO_MAX_DAYS_COLD}")
    lamps.append(
        {
            "id": "eco_stress",
            "name": "生态恶化",
            "red": bool(eco_reasons),
            "kind": "hard",
            "weight": 1.0,
            "detail": "；".join(eco_reasons) if eco_reasons else (
                f"昨亏{yest_loss} / 跌停{dt} / 高标{max_days}板"
            ),
        }
    )

    # 4 业绩窗口（软）
    earn = is_earnings_window()
    lamps.append(
        {
            "id": "earnings",
            "name": "业绩窗口",
            "red": earn,
            "kind": "soft",
            "weight": 1.0,
            "detail": "披露高峰窗口" if earn else "非业绩窗口",
        }
    )

    # 5 杠杆退潮（软·手动）
    lamps.append(
        {
            "id": "leverage",
            "name": "杠杆退潮",
            "red": bool(lever_red),
            "kind": "soft",
            "weight": 1.0,
            "manual": True,
            "detail": "已手动标记两融退潮" if lever_red else "未标记（网页可点）",
        }
    )
    return lamps
