"""市场情绪温度采样（与 frontend signals.js computeSentimentBrief 同口径）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.infrastructure.market.service import market
from app.services.lamps import compute_lamps, lamp_cap_from_lamps

_CN_TZ = ZoneInfo("Asia/Shanghai")
_SENTIMENT_FILE = "sentiment_temp_intraday.json"
ICE_BAND = 35  # 谨慎/偏冷参考带上沿（与 phase cold 阈值对齐）
BOIL_BAND = 78  # 偏热/亢奋参考线（与 temp≥78 对齐）
_META_KEYS = frozenset({"close", "maxDays"})
# 折线用近一月交易日（约 22 个点）；文件多留几天日历缓冲
_CHART_TRADING_DAYS = 22
_KEEP_CALENDAR_DAYS = 45


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _path() -> Path:
    return Path(settings.data_dir) / _SENTIMENT_FILE


def _hhmm(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _short_day(day: str) -> str:
    """2026-08-07 -> 08-07"""
    if len(day) >= 10:
        return day[5:10]
    return day


def _day_close(series: dict[str, float]) -> float | None:
    if not series:
        return None
    if "close" in series:
        try:
            return float(series["close"])
        except (TypeError, ValueError):
            pass
    keys = sorted(k for k in series.keys() if k not in _META_KEYS and ":" in str(k))
    if not keys:
        return None
    try:
        return float(series[keys[-1]])
    except (TypeError, ValueError):
        return None


def _day_height(series: dict[str, float]) -> int | None:
    if not series or "maxDays" not in series:
        return None
    try:
        v = int(round(float(series["maxDays"])))
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def _load_days() -> dict[str, dict[str, float]]:
    p = _path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for day, series in raw.items():
        if not isinstance(series, dict):
            continue
        clean: dict[str, float] = {}
        for k, v in series.items():
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            # 温度 0–100；最高板允许到 20
            if k == "maxDays":
                if 0 <= fv <= 20:
                    clean[str(k)] = fv
            elif 0 <= fv <= 100:
                clean[str(k)] = fv
        if clean:
            out[str(day)] = clean
    return out


def _compress_and_trim(days: dict[str, dict[str, float]], today: str) -> dict[str, dict[str, float]]:
    """历史日只留收盘点+最高板；今日保留分钟序列；裁到近 _KEEP_CALENDAR_DAYS。"""
    for d, series in list(days.items()):
        if d >= today:
            continue
        close = _day_close(series)
        if close is None:
            del days[d]
        else:
            row: dict[str, float] = {"close": float(close)}
            h = _day_height(series)
            if h is not None:
                row["maxDays"] = float(h)
            days[d] = row
    keep_keys = sorted(days.keys())[-_KEEP_CALENDAR_DAYS:]
    return {d: days[d] for d in keep_keys}


def _save_days(days: dict[str, dict[str, float]], today: str) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        trimmed = _compress_and_trim(dict(days), today)
        # 写回内存裁剪结果
        days.clear()
        days.update(trimmed)
        p.write_text(json.dumps(trimmed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass


def _sentiment_retreat(mb: dict[str, Any], breadth: dict[str, Any]) -> bool:
    src = mb if (mb.get("total") or 0) > 0 else breadth
    total = int(src.get("total") or 0)
    if total <= 0:
        return False
    up = int(src.get("up") or 0)
    up_pct = up / total
    if up_pct < 0.4:
        return True
    if (mb.get("total") or 0) > 0 and up < 1500:
        return True
    return False


def compute_sentiment_temp(*, lever_red: bool = False) -> int | None:
    """合成温度 0–100；广度不足时返回 None。"""
    mb = market.market_breadth or {}
    breadth = market.breadth or {}
    src = mb if (mb.get("total") or 0) > 0 else breadth
    up = int(src.get("up") or 0)
    down = int(src.get("down") or 0)
    flat = int(src.get("flat") or 0)
    total = int(src.get("total") or (up + down + flat))
    if total <= 0:
        return None
    up_pct = up / total

    lu = market.limit_up_stats or {}
    zt = int(lu.get("zt") or 0)
    zb = int(lu.get("zb") or 0)
    dt = int(lu.get("dt") or 0)
    max_days = int(lu.get("maxDays") or 0)
    break_rate = lu.get("breakRate")
    if break_rate is not None:
        try:
            break_rate = float(break_rate)
        except (TypeError, ValueError):
            break_rate = None
    elif zt + zb > 0:
        break_rate = round(zb / (zt + zb) * 1000) / 10
    yest_premium = lu.get("yestPremium")
    if yest_premium is not None:
        try:
            yest_premium = float(yest_premium)
        except (TypeError, ValueError):
            yest_premium = None
    promote_rate = lu.get("promoteRate")
    if promote_rate is not None:
        try:
            promote_rate = float(promote_rate)
        except (TypeError, ValueError):
            promote_rate = None
    big_drawdown = int(lu.get("bigDrawdown") or 0)

    lamps = compute_lamps(lever_red=lever_red)
    risk_score = float(lamp_cap_from_lamps(lamps).get("riskScore") or 0)
    retreat = _sentiment_retreat(mb, breadth)

    temp = 48.0
    temp += (up_pct - 0.5) * 55
    temp += _clamp(zt / 5, 0, 14)
    if max_days >= 5:
        temp += 8
    elif max_days >= 3:
        temp += 4
    if dt > 40:
        temp -= 10
    elif dt > 20:
        temp -= 5
    if break_rate is not None:
        if break_rate >= 45:
            temp -= 10
        elif break_rate >= 30:
            temp -= 5
        elif break_rate <= 15 and zt >= 20:
            temp += 4
    if yest_premium is not None:
        temp += _clamp(yest_premium * 1.8, -12, 12)
    if promote_rate is not None:
        if promote_rate >= 35:
            temp += 6
        elif promote_rate >= 20:
            temp += 3
        elif promote_rate < 10:
            temp -= 6
    if big_drawdown >= 25:
        temp -= 10
    elif big_drawdown >= 12:
        temp -= 5
    if retreat:
        temp -= 18
    temp -= min(18.0, risk_score * 4)
    return int(round(_clamp(temp, 0, 100)))


def _ensure_days() -> dict[str, dict[str, float]]:
    """从磁盘灌入历史；避免 MarketService 空 dict 挡住首次加载。"""
    days = getattr(market, "_sentiment_days", None)
    if isinstance(days, dict) and days:
        return days
    loaded = _load_days()
    if isinstance(days, dict):
        # 已是空 dict：原地灌入，保持引用
        days.clear()
        days.update(loaded)
        return days
    market._sentiment_days = loaded
    return loaded


def sample_sentiment_temp() -> None:
    """盘中按分钟写入；折线图用近一月「日点」+ 今日实时末点。"""
    now = datetime.now(_CN_TZ)
    today = now.strftime("%Y-%m-%d")
    days = _ensure_days()

    weekend = now.weekday() >= 5
    in_session = (not weekend) and (
        (now.hour > 9 or (now.hour == 9 and now.minute >= 25))
        and (now.hour < 15 or (now.hour == 15 and now.minute <= 5))
    )
    after_close = (not weekend) and (
        now.hour > 15 or (now.hour == 15 and now.minute > 5)
    )

    temp = None if weekend else compute_sentiment_temp()
    lu = market.limit_up_stats or {}
    try:
        live_height = int(lu.get("maxDays") or 0)
    except (TypeError, ValueError):
        live_height = 0

    if temp is not None and (in_session or after_close):
        series = days.setdefault(today, {})
        if in_session:
            bucket = _hhmm(now)
            prev = series.get(bucket)
            if prev is None or abs(prev - float(temp)) >= 0.5:
                series[bucket] = float(temp)
        # 收盘后 / 盘中持续刷新 close，作「今日日点」底稿
        series["close"] = float(temp)
        if live_height > 0:
            series["maxDays"] = float(live_height)
        _save_days(days, today)

    market.sentiment_history = _history_payload(now, temp, live_height if live_height > 0 else None)


def _history_payload(
    now: datetime,
    temp: int | None,
    live_height: int | None = None,
) -> dict[str, Any]:
    days = _ensure_days()
    today = now.strftime("%Y-%m-%d")
    day_keys = sorted(days.keys())
    # 只取有收盘/样本的交易日，近 _CHART_TRADING_DAYS 个
    dated: list[tuple[str, float, int | None]] = []
    for d in day_keys:
        close = _day_close(days[d])
        if close is None:
            continue
        dated.append((d, close, _day_height(days[d])))
    dated = dated[-_CHART_TRADING_DAYS:]

    points: list[dict[str, Any]] = []
    height_points: list[dict[str, Any]] = []
    for d, close, height in dated:
        live = d == today and temp is not None
        points.append({
            "t": _short_day(d),
            "day": d,
            "v": int(round(temp if live else close)),
            "live": live,
        })
        hv = live_height if (d == today and live_height is not None) else height
        if hv is not None and hv >= 0:
            height_points.append({
                "t": _short_day(d),
                "day": d,
                "v": int(hv),
                "live": d == today and live_height is not None,
            })

    # 今日尚无历史文件、但已有实时温度 → 补一个末点
    if temp is not None and not any(p.get("day") == today for p in points):
        points.append({
            "t": _short_day(today),
            "day": today,
            "v": int(round(temp)),
            "live": True,
        })
        if len(points) > _CHART_TRADING_DAYS:
            points = points[-_CHART_TRADING_DAYS:]
    if live_height is not None and not any(p.get("day") == today for p in height_points):
        height_points.append({
            "t": _short_day(today),
            "day": today,
            "v": int(live_height),
            "live": True,
        })
        if len(height_points) > _CHART_TRADING_DAYS:
            height_points = height_points[-_CHART_TRADING_DAYS:]

    n = len(points)
    if n <= 1:
        note = (
            "情绪温度按交易日沉淀；当前仅有少量样本，折线会随开市日增多"
            "（约一个月约 22 个点）。周末不采样。"
        )
    elif n < 8:
        note = f"近一月交易日温度（已沉淀 {n} 日）；末点=今日实时。样本仍偏少，曲线会逐渐拉长。"
    else:
        note = "近一月交易日温度（历史=当日收盘点）；末点=今日实时，随盘面刷新"

    return {
        "day": today,
        "temp": temp,
        "iceBand": ICE_BAND,
        "boilBand": BOIL_BAND,
        "maxDays": live_height,
        "range": "1m",
        "rangeLabel": "近一月",
        "points": points,
        "heightPoints": height_points,
        "note": note,
    }


def sentiment_history_snapshot() -> dict[str, Any]:
    now = datetime.now(_CN_TZ)
    weekend = now.weekday() >= 5
    temp = None if weekend else compute_sentiment_temp()
    hist = getattr(market, "sentiment_history", None)
    if temp is None and isinstance(hist, dict) and hist.get("temp") is not None:
        try:
            temp = int(hist["temp"])
        except (TypeError, ValueError):
            temp = None
    lu = market.limit_up_stats or {}
    try:
        live_height = int(lu.get("maxDays") or 0) or None
    except (TypeError, ValueError):
        live_height = None
    if live_height is None and isinstance(hist, dict) and hist.get("maxDays") is not None:
        try:
            live_height = int(hist["maxDays"]) or None
        except (TypeError, ValueError):
            live_height = None
    return _history_payload(now, temp, live_height)
