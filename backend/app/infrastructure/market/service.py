from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.infrastructure.persistence.watch_store import load_watch_codes, save_watch_codes

INDEX_CODES = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300"]
_CN_TZ = ZoneInfo("Asia/Shanghai")
_TURNOVER_FILE = "market_turnover_intraday.json"
_INDUSTRY_FILE = "stock_industry.json"

DEFAULT_CODES = [
    "sz002463", "sz002916", "sz300502", "sz300408", "sz002156",
    "sh600584", "sz300604", "sz002371", "sz002409",
    "sz301308", "sh603986", "sz300480", "sz300394",
    "sz000636", "sz300308", "sh688256", "sh688041", "sh688981",
    "sh603629", "sz000815", "sz300442", "sz301396", "sh600536",
    "sh515050", "sh513310", "sh562500", "sh562590",
    "sz159300", "sh588000", "sz159659", "sh513090",
    "sz159740", "sh513330", "sh515220", "sz159330",
]

# 盘后选股 / 竞价扫描宇宙（精选宽池，非全 A）
SCREEN_UNIVERSE = [
    "sz002463", "sz002916", "sz300502", "sz300394", "sz300408", "sz002156",
    "sh600584", "sz300604", "sz002371", "sz300308", "sh603986", "sh603290",
    "sz002049", "sz300661", "sh688012", "sh688256", "sh688041", "sh688981",
    "sz300223", "sz300782", "sh603160", "sz300666", "sz002475", "sz000725",
    "sh600183", "sz002384", "sh603629", "sz000636", "sz301396",
    "sz002230", "sh600536", "sz000815", "sz002405", "sz300033", "sh688111",
    "sz300059", "sh600588", "sz000977", "sz002236",
    "sz300750", "sz002594", "sh601012", "sh600438", "sz300274", "sz002709",
    "sz300037", "sz002460", "sz002466",
    "sz000768", "sh600760", "sz002179", "sh600893",
    "sz300015", "sh600276", "sz000538", "sh600436", "sz300760",
    "sh600036", "sh601318", "sh600030", "sh601688",
    "sh600519", "sz000858", "sh600887", "sz000333", "sz000651",
    "sh601168", "sz002493", "sh600309", "sz002340",
    "sh601138", "sz002008", "sh601100", "sh600009",
    "sh600050", "sz000063", "sh601728",
    "sh600104", "sz000625", "sh601238",
]


def _load_codes() -> list[str]:
    codes = list(DEFAULT_CODES)
    extra = load_watch_codes()
    if isinstance(extra, list):
        for c in extra:
            if isinstance(c, str) and c and c not in codes:
                codes.append(c)
    return codes


class MarketService:
    def __init__(self) -> None:
        self.stock_codes = _load_codes()
        self.quote_cache: dict[str, dict] = {}
        self.index_cache: dict[str, dict] = {}
        self.kline_cache: dict[str, dict] = {}
        self.breadth = {"up": 0, "down": 0, "flat": 0, "total": 0}
        self.market_breadth = {"up": 0, "down": 0, "flat": 0, "total": 0, "source": "自选"}
        self.overseas: dict | None = None
        self.limit_up_stats = {
            "zt": 0,
            "zb": 0,
            "dt": 0,
            "maxDays": 0,
            "topSector": "",
            "ladder": {},
            "breakRate": None,
            "yestPremium": None,
            "yestPremiumSample": 0,
            "promoteRate": None,
            "promoteEligible": 0,
            "promoteSuccess": 0,
            "bigDrawdown": 0,
            "bigDrawdownThr": -5.0,
            "yestLoss": 0,
            "source": "",
            "lastUpdate": None,
        }
        self.sector_flow_cache = {
            "summary": {"totalNetInflow": 0.0, "positiveCount": 0, "total": 0, "topSector": None},
            "list": [],
            "source": "",
            "lastUpdate": None,
        }
        self._sector_flow_history: list[tuple[datetime, dict[str, float]]] = []
        self.market_turnover: dict[str, Any] = {
            "amountYi": None,
            "amountWan": None,
            "deltaYi": None,
            "shAmountYi": None,
            "szAmountYi": None,
            "bucket": None,
            "day": None,
            "prevDay": None,
            "source": "沪+深成交额（≈三市，未含北交所）",
            "deltaSource": "较上日此时",
            "ready": False,
            "note": "",
        }
        self._turnover_days: dict[str, dict[str, float]] = {}
        self._load_turnover_history()
        self._turnover_delta_cache: dict[str, Any] = {"ts": 0.0, "deltaYi": None, "prevDay": None, "note": ""}
        self._sentiment_days: dict[str, dict[str, float]] | None = None
        self.sentiment_history: dict[str, Any] = {
            "day": None,
            "temp": None,
            "iceBand": 35,
            "boilBand": 78,
            "range": "1m",
            "rangeLabel": "近一月",
            "points": [],
            "heightPoints": [],
            "note": "",
        }
        self.last_update: str | None = None
        self.last_kline_update: str | None = None
        self.last_aux_update: str | None = None
        self.last_sector_flow_update: str | None = None
        self._fetching = False
        self._fetching_aux = False
        self._fetching_sector_flow = False
        self._fetching_k = False
        self._industry_cache: dict[str, str] = {}
        self._load_industry_cache()

    def _turnover_path(self) -> Path:
        return Path(settings.data_dir) / _TURNOVER_FILE

    def _industry_path(self) -> Path:
        return Path(settings.data_dir) / _INDUSTRY_FILE

    def _load_industry_cache(self) -> None:
        p = self._industry_path()
        if not p.exists():
            return
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._industry_cache = {
                    str(k): str(v).strip()
                    for k, v in raw.items()
                    if str(k).strip() and str(v).strip()
                }
        except Exception:
            self._industry_cache = {}

    def _save_industry_cache(self) -> None:
        p = self._industry_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(self._industry_cache, ensure_ascii=False, indent=0, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            pass

    @staticmethod
    def _em_secid(code: str) -> str | None:
        from app.domain.sectors import raw_code

        c = raw_code(code)
        if len(c) != 6 or not c.isdigit():
            return None
        # 沪市 6/5/9；深市 0/1/2/3；北交所 4/8 用 0. 亦可，东财常用 0.
        if c.startswith(("5", "6", "9")):
            return f"1.{c}"
        return f"0.{c}"

    def industry_of(self, code: str) -> str:
        from app.domain.sectors import raw_code

        c = raw_code(code)
        return self._industry_cache.get(c) or ""

    async def ensure_industries(self, codes: list[str] | None = None) -> dict[str, str]:
        """批量补全东财行业名（f100），写入缓存并挂到 quote。"""
        from app.domain.sectors import raw_code

        want = list(dict.fromkeys(raw_code(c) for c in (codes or self.stock_codes) if c))
        missing = [c for c in want if c and c not in self._industry_cache]
        if missing:
            batches = [missing[i : i + 40] for i in range(0, len(missing), 40)]
            async with httpx.AsyncClient() as client:
                for batch in batches:
                    secids = ",".join(
                        sid for c in batch if (sid := self._em_secid(c))
                    )
                    if not secids:
                        continue
                    url = (
                        "https://push2.eastmoney.com/api/qt/ulist.np/get"
                        f"?fltt=2&secids={secids}&fields=f12,f14,f100"
                        "&ut=fa5fd1943c7b386f172d6893dbfba10b"
                    )
                    try:
                        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
                        diffs = (r.json().get("data") or {}).get("diff") or []
                        if isinstance(diffs, dict):
                            diffs = list(diffs.values())
                        for d in diffs:
                            rc = str(d.get("f12") or "").strip()
                            ind = str(d.get("f100") or "").strip()
                            if rc and ind:
                                self._industry_cache[rc] = ind
                    except Exception:
                        continue
            self._save_industry_cache()

        # 挂到现有 quote（供前端 liveScore / 展示）
        for code, q in list(self.quote_cache.items()):
            ind = self.industry_of(code)
            if ind and isinstance(q, dict):
                q["industry"] = ind
        return {c: self._industry_cache[c] for c in want if c in self._industry_cache}

    def _load_turnover_history(self) -> None:
        p = self._turnover_path()
        if not p.exists():
            return
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                clean: dict[str, dict[str, float]] = {}
                for day, series in raw.items():
                    if not isinstance(series, dict):
                        continue
                    clean[str(day)] = {
                        str(k): float(v)
                        for k, v in series.items()
                        if isinstance(v, (int, float)) and float(v) > 0
                    }
                self._turnover_days = clean
        except Exception:
            self._turnover_days = {}

    def _save_turnover_history(self) -> None:
        p = self._turnover_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # 只留最近 12 个交易日曲线
            days = sorted(self._turnover_days.keys())
            keep = {d: self._turnover_days[d] for d in days[-12:]}
            self._turnover_days = keep
            p.write_text(json.dumps(keep, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _cn_now() -> datetime:
        return datetime.now(_CN_TZ)

    @staticmethod
    def _hhmm(dt: datetime) -> str:
        return f"{dt.hour:02d}:{dt.minute:02d}"

    @staticmethod
    def _lookup_bucket(series: dict[str, float], bucket: str) -> float | None:
        if not series:
            return None
        if bucket in series:
            return float(series[bucket])
        # 找 ±5 分钟内最近采样
        try:
            h, m = map(int, bucket.split(":"))
            base = h * 60 + m
        except Exception:
            return None
        best = None
        best_dist = 99
        for k, v in series.items():
            try:
                hh, mm = map(int, str(k).split(":"))
            except Exception:
                continue
            dist = abs(hh * 60 + mm - base)
            if dist <= 5 and dist < best_dist:
                best_dist = dist
                best = float(v)
        return best

    @staticmethod
    def _amount_raw_to_yi(raw: float) -> float | None:
        """成交额原始值 → 亿元。东财分时多为「元」；兼容万元。"""
        v = float(raw or 0)
        if not (v > 0):
            return None
        if v >= 1e8:  # 元（单分钟也常 >1e8）
            return v / 1e8
        if v >= 1e4:  # 万元
            return v / 1e4
        return v

    @staticmethod
    def _parse_em_trends(trends: list[Any]) -> dict[str, dict[str, float]]:
        """date -> {HH:MM -> amountYi}（累计成交额）。

        东财 trends2 fields2：f51 时间, f52..f55 价, f56 量, f57 额, f58 均价。
        f57（parts[6]）是当分钟成交额，需按日累加；push2 / push2delay 的 ndays=2
        常只返回当日，历史对比请走 push2his。
        """
        by_day: dict[str, list[tuple[str, float]]] = {}
        for row in trends or []:
            if not isinstance(row, str):
                continue
            parts = row.split(",")
            # 至少要有 f57 成交额
            if len(parts) < 7:
                continue
            ts = parts[0].strip()
            if len(ts) < 16:
                continue
            day = ts[:10]
            hhmm = ts[11:16]
            try:
                amt = float(parts[6] or 0)
            except (TypeError, ValueError):
                continue
            if amt <= 0:
                continue
            by_day.setdefault(day, []).append((hhmm, amt))

        out: dict[str, dict[str, float]] = {}
        for day, items in by_day.items():
            # 若序列近似单调递增且末值接近总和，视为已是累计额
            amounts = [a for _, a in items]
            total = sum(amounts)
            last = amounts[-1] if amounts else 0.0
            looks_cum = last >= total * 0.85 and all(
                amounts[i] <= amounts[i + 1] * 1.001 + 1 for i in range(len(amounts) - 1)
            )
            series: dict[str, float] = {}
            cum = 0.0
            for hhmm, amt in items:
                if looks_cum:
                    yi = MarketService._amount_raw_to_yi(amt)
                else:
                    cum += amt
                    yi = MarketService._amount_raw_to_yi(cum)
                if yi is None:
                    continue
                series[hhmm] = yi
            if series:
                out[day] = series
        return out

    async def _em_json(self, url: str) -> dict[str, Any]:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        for trust_env in (True, False):
            try:
                async with httpx.AsyncClient(trust_env=trust_env, timeout=12.0) as client:
                    r = await client.get(url, headers=headers)
                    j = r.json()
                    if isinstance(j, dict):
                        return j
            except Exception:
                continue
        return {}

    async def _fetch_em_index_trends(self, secid: str) -> list[Any]:
        """拉取指数分时；优先 push2his（ndays=2 才有昨+今）。"""
        q = (
            "?fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=2"
            f"&ut=fa5fd1943c7b386f172d6893dbfba10b&secid={secid}"
        )
        hosts = (
            "https://push2his.eastmoney.com/api/qt/stock/trends2/get",
            "https://push2delay.eastmoney.com/api/qt/stock/trends2/get",
            "https://push2.eastmoney.com/api/qt/stock/trends2/get",
        )
        best: list[Any] = []
        best_days = 0
        for host in hosts:
            j = await self._em_json(f"{host}{q}")
            trends = ((j.get("data") or {}).get("trends") or []) if isinstance(j, dict) else []
            if not isinstance(trends, list) or not trends:
                continue
            days = {
                str(row).split(",")[0][:10]
                for row in trends
                if isinstance(row, str) and len(str(row)) >= 16
            }
            n = len(days)
            if n > best_days:
                best = trends
                best_days = n
            if n >= 2:
                return trends
        return best

    async def _enrich_turnover_delta_from_em(self) -> None:
        """用东财指数分时 ndays=2 计算「较上日此时」（沪+深）。"""
        now_ts = time.time()
        cache = self._turnover_delta_cache
        # 60s 内有成功结果则直接回填；超时后仍可重新拉东财
        if cache.get("ts") and now_ts - float(cache["ts"]) < 60 and cache.get("deltaYi") is not None:
            if self.market_turnover.get("amountYi"):
                self.market_turnover["deltaYi"] = cache.get("deltaYi")
                self.market_turnover["prevDay"] = cache.get("prevDay")
                self.market_turnover["ready"] = True
                self.market_turnover["note"] = cache.get("note") or self.market_turnover.get("note")
            return

        sh_trends, sz_trends = await asyncio.gather(
            self._fetch_em_index_trends("1.000001"),
            self._fetch_em_index_trends("0.399001"),
        )
        sh_map = self._parse_em_trends(sh_trends)
        sz_map = self._parse_em_trends(sz_trends)
        # 必须沪、深两边都有该日，避免深市缺失时把「仅上证」当成三市
        days = sorted(set(sh_map.keys()) & set(sz_map.keys()))
        if len(days) < 2:
            # 仅当日时无法算「较上日」；保留本机采样路径，不覆盖已有 delta
            if not self.market_turnover.get("deltaYi"):
                self.market_turnover["note"] = "东财分时暂无昨日曲线，等待本机采样或稍后重试"
            return
        today, yest = days[-1], days[-2]
        # 取今日最新「沪深都有」的分钟
        today_keys = sorted(set(sh_map.get(today, {})) & set(sz_map.get(today, {})))
        if not today_keys:
            return
        bucket = today_keys[-1]

        def _sum_at(day: str, hhmm: str) -> float | None:
            sh = (sh_map.get(day) or {}).get(hhmm)
            sz = (sz_map.get(day) or {}).get(hhmm)
            if sh is None or sz is None:
                return None
            return float(sh) + float(sz)

        def _lookup_day(day: str, hhmm: str) -> float | None:
            v = _sum_at(day, hhmm)
            if v is not None:
                return v
            try:
                h, m = map(int, hhmm.split(":"))
                base_m = h * 60 + m
            except Exception:
                return None
            for dist in range(1, 6):
                for sign in (-1, 1):
                    mm = base_m + sign * dist
                    if mm < 0:
                        continue
                    alt = f"{mm // 60:02d}:{mm % 60:02d}"
                    v = _sum_at(day, alt)
                    if v is not None:
                        return v
            return None

        today_yi = _lookup_day(today, bucket)
        yest_yi = _lookup_day(yest, bucket)
        if today_yi is None or yest_yi is None or yest_yi <= 0:
            return

        delta_yi = round(today_yi - yest_yi, 1)
        # 差额异常则不回写污染本机曲线
        if abs(delta_yi) > max(3500.0, today_yi * 0.28):
            if not self.market_turnover.get("deltaYi"):
                self.market_turnover["note"] = "东财较上日差额异常，已忽略"
            return

        note = f"东财分时 · 较 {yest} {bucket}（沪+深）"
        self._turnover_delta_cache = {
            "ts": now_ts,
            "deltaYi": delta_yi,
            "prevDay": yest,
            "note": note,
            "bucket": bucket,
            "todayYi": round(today_yi, 1),
        }
        # 回填本机采样（万元）；只写沪深双全的分钟，整日覆盖掉旧的半套脏数据
        try:
            for day in (today, yest):
                keys = sorted(set(sh_map.get(day, {})) & set(sz_map.get(day, {})))
                fresh: dict[str, float] = {}
                for hhmm in keys:
                    yi = _sum_at(day, hhmm)
                    if yi and yi > 0:
                        fresh[hhmm] = yi * 10000
                if fresh:
                    self._turnover_days[day] = fresh
            self._save_turnover_history()
        except Exception:
            pass

        mt = self.market_turnover
        mt["deltaYi"] = delta_yi
        mt["prevDay"] = yest
        mt["bucket"] = bucket
        mt["ready"] = True
        mt["note"] = note
        mt["deltaSource"] = "较上日此时"
        # 若腾讯额异常，可用东财合计校正展示
        if not mt.get("amountYi") or abs(float(mt["amountYi"]) - today_yi) / max(today_yi, 1) > 0.25:
            mt["amountYi"] = round(today_yi, 1)
            mt["source"] = "东财分时沪+深（≈三市，未含北交所）"

    def _update_market_turnover(self) -> None:
        """沪+深成交额合计≈三市；较上日此时优先东财分时，其次本机采样。"""
        sh = self.index_cache.get("sh000001") or {}
        sz = self.index_cache.get("sz399001") or {}
        sh_wan = float(sh.get("amount") or 0)
        sz_wan = float(sz.get("amount") or 0)
        if sh_wan <= 0 or sz_wan <= 0:
            return
        total_wan = sh_wan + sz_wan
        today_yi = total_wan / 10000
        now = self._cn_now()
        day = now.strftime("%Y-%m-%d")
        bucket = self._hhmm(now)
        in_session = (now.hour > 9 or (now.hour == 9 and now.minute >= 25)) and (
            now.hour < 15 or (now.hour == 15 and now.minute <= 5)
        )
        if in_session and not (now.weekday() >= 5):
            series = self._turnover_days.setdefault(day, {})
            prev = series.get(bucket)
            if prev is None or abs(prev - total_wan) / max(prev, 1) > 0.0005:
                series[bucket] = total_wan
                self._save_turnover_history()

        prev_day = None
        prev_wan = None
        for d in sorted(self._turnover_days.keys(), reverse=True):
            if d < day:
                prev_wan = self._lookup_bucket(self._turnover_days[d], bucket)
                if prev_wan:
                    prev_day = d
                    break

        delta_yi = None
        ready = False
        note = "较上日此时拉取中…"
        if prev_wan and prev_wan > 0:
            local_delta = round((total_wan - prev_wan) / 10000, 1)
            # 本机采样若与今日额量级差太多（常见于历史被错误源污染），丢弃以免出现「+1万亿」
            prev_yi = prev_wan / 10000
            scale_ok = 0.55 * today_yi <= prev_yi <= 1.8 * today_yi
            mag_ok = abs(local_delta) <= max(3500.0, today_yi * 0.28)
            if scale_ok and mag_ok:
                delta_yi = local_delta
                ready = True
                note = f"本机采样 · 较 {prev_day} {bucket}（沪+深）"
            else:
                note = "本机昨额量级异常，改用东财分时…"

        # 东财缓存优先（更接近同花顺「较上日此时」）；放宽到 15 分钟
        cache = self._turnover_delta_cache or {}
        if cache.get("deltaYi") is not None and cache.get("ts"):
            if time.time() - float(cache["ts"]) < 900:
                delta_yi = cache.get("deltaYi")
                prev_day = cache.get("prevDay")
                ready = True
                note = cache.get("note") or note
                if cache.get("bucket"):
                    bucket = str(cache["bucket"])

        self.market_turnover = {
            "amountYi": round(today_yi, 1),
            "amountWan": total_wan,
            "deltaYi": delta_yi,
            "shAmountYi": round(sh_wan / 10000, 1),
            "szAmountYi": round(sz_wan / 10000, 1),
            "bucket": bucket,
            "day": day,
            "prevDay": prev_day,
            "source": "沪+深成交额（≈三市，未含北交所）",
            "deltaSource": "较上日此时",
            "ready": ready,
            "note": note,
        }

    def save_codes(self) -> None:
        save_watch_codes(self.stock_codes)

    def reload_codes(self) -> None:
        self.stock_codes = _load_codes()

    @staticmethod
    def parse_tencent_quote(line: str) -> dict | None:
        m = re.search(r'v_(\w+)="([^"]+)"', line)
        if not m:
            return None
        code, payload = m.group(1), m.group(2)
        fields = payload.split("~")
        if len(fields) < 30:
            return None
        bid = sum(int(fields[i] or 0) for i in (10, 12, 14, 16, 18))
        ask = sum(int(fields[i] or 0) for i in (20, 22, 24, 26, 28))
        weibi = ((bid - ask) / (bid + ask) * 100) if (bid + ask) else 0
        return {
            "code": code,
            "name": fields[1] or "",
            "price": float(fields[3] or 0),
            "prevClose": float(fields[4] or 0),
            "open": float(fields[5] or 0),
            "volume": int(float(fields[6] or 0)),
            "high": float(fields[33] or 0) if len(fields) > 33 else 0,
            "low": float(fields[34] or 0) if len(fields) > 34 else 0,
            "amount": float(fields[37] or 0) if len(fields) > 37 else 0,
            "weibi": round(weibi, 2),
            "change": float(fields[31] or 0) if len(fields) > 31 else 0,
            "changePct": float(fields[32] or 0) if len(fields) > 32 else 0,
            "turnover": float(fields[38] or 0) if len(fields) > 38 else 0,
            "liangbi": float(fields[43] or 0) if len(fields) > 43 else 0,
            "totalMktCap": float(fields[44] or 0) if len(fields) > 44 else 0,
            "floatMktCap": float(fields[45] or 0) if len(fields) > 45 else 0,
            "pb": float(fields[46] or 0) if len(fields) > 46 else 0,
            "limitUp": float(fields[47] or 0) if len(fields) > 47 else 0,
            "limitDown": float(fields[48] or 0) if len(fields) > 48 else 0,
            "amplitude": float(fields[49] or 0) if len(fields) > 49 else 0,
            "pe": float(fields[52] or 0) if len(fields) > 52 else 0,
            "peTTM": float(fields[53] or 0) if len(fields) > 53 else 0,
        }

    async def _fetch_quotes_batch(self, client: httpx.AsyncClient, codes: list[str]) -> dict[str, dict]:
        url = "http://qt.gtimg.cn/q=" + ",".join(codes)
        try:
            r = await client.get(url, timeout=10.0)
            r.raise_for_status()
            # Tencent often returns gbk; httpx may decode as latin-1/utf-8 incorrectly
            text = r.content.decode("gbk", errors="ignore")
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for line in text.splitlines():
            q = self.parse_tencent_quote(line.strip())
            if q and q["price"] > 0:
                out[q["code"]] = q
        return out

    async def fetch_all_quotes(self) -> None:
        """高频：腾讯报价 + 全市场涨跌统计（轻量）。"""
        if self._fetching:
            return
        self._fetching = True
        try:
            all_codes = self.stock_codes + INDEX_CODES
            batches = [all_codes[i : i + 20] for i in range(0, len(all_codes), 20)]
            async with httpx.AsyncClient() as client:
                results = await asyncio.gather(*[self._fetch_quotes_batch(client, b) for b in batches])
                await self._fetch_market_breadth(client)
            up = down = flat = 0
            for batch in results:
                for code, q in batch.items():
                    if code in INDEX_CODES:
                        self.index_cache[code] = q
                    else:
                        self.quote_cache[code] = q
                        if q["changePct"] > 0:
                            up += 1
                        elif q["changePct"] < 0:
                            down += 1
                        else:
                            flat += 1
            self.breadth = {"up": up, "down": down, "flat": flat, "total": up + down + flat}
            active = set(self.stock_codes)
            for c in list(self.quote_cache.keys()):
                if c not in active:
                    del self.quote_cache[c]
            self._update_market_turnover()
            try:
                await self._enrich_turnover_delta_from_em()
            except Exception:
                pass
            try:
                from app.services.sentiment import sample_sentiment_temp

                sample_sentiment_temp()
            except Exception:
                pass
            try:
                await self.ensure_industries(self.stock_codes)
            except Exception:
                pass
            self.last_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching = False

    async def fetch_market_aux(self) -> None:
        """低频：海外指数、涨停池（东财较重）。"""
        if self._fetching_aux:
            return
        self._fetching_aux = True
        try:
            async with httpx.AsyncClient() as client:
                await asyncio.gather(
                    self._fetch_overseas(client),
                    self._fetch_limit_up_stats(client),
                )
            try:
                from app.services.sentiment import sample_sentiment_temp

                sample_sentiment_temp()
            except Exception:
                pass
            self.last_aux_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching_aux = False

    async def fetch_sector_flow(self) -> None:
        """中频：板块资金流向。"""
        if self._fetching_sector_flow:
            return
        self._fetching_sector_flow = True
        try:
            async with httpx.AsyncClient() as client:
                await self._fetch_sector_flow(client)
            self.last_sector_flow_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching_sector_flow = False

    async def _fetch_market_breadth(self, client: httpx.AsyncClient) -> None:
        url = (
            "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
            "?fltt=2&secids=1.000001,0.399001,0.899050&fields=f104,f105,f106"
            "&ut=fa5fd1943c7b386f172d6893dbfba10b"
        )
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8.0)
            j = r.json()
            diffs = (j.get("data") or {}).get("diff") or []
            up = down = flat = 0
            for d in diffs:
                up += d.get("f104") or 0
                down += d.get("f105") or 0
                flat += d.get("f106") or 0
            if up + down + flat > 0:
                self.market_breadth = {
                    "up": up, "down": down, "flat": flat, "total": up + down + flat, "source": "全市场"
                }
        except Exception:
            pass

    async def _fetch_overseas(self, client: httpx.AsyncClient) -> None:
        """拉取美/日/韩主要指数（东财延时行情）。"""

        async def _one(secid: str, code: str, name: str) -> dict[str, Any] | None:
            url = (
                "https://push2delay.eastmoney.com/api/qt/stock/get"
                f"?secid={secid}&fields=f43,f170&ut=fa5fd1943c7b386f172d6893dbfba10b"
            )
            try:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8.0)
                d = (r.json().get("data") or {})
                if (d.get("f43") or 0) <= 0:
                    return None
                return {
                    "code": code,
                    "name": name,
                    "price": round((d.get("f43") or 0) / 100, 2),
                    "changePct": (d.get("f170") or 0) / 100,
                    "lastUpdate": datetime.now(timezone.utc).isoformat(),
                }
            except Exception:
                return None

        spx, ndx, nikkei, kospi = await asyncio.gather(
            _one("100.SPX", "SPX", "标普500"),
            _one("100.NDX", "NDX", "纳斯达克100"),
            _one("100.N225", "N225", "日经225"),
            _one("100.KS11", "KS11", "韩国KOSPI"),
        )
        base = spx or {
            "code": "SPX",
            "name": "标普500",
            "price": None,
            "changePct": None,
            "lastUpdate": None,
        }
        extras: dict[str, Any] = {}
        if ndx:
            extras["nasdaq"] = ndx
        if nikkei:
            extras["nikkei"] = nikkei
        if kospi:
            extras["kospi"] = kospi
        # 至少有一个外围指数才写入缓存
        if spx or ndx or nikkei or kospi:
            last = None
            for x in (spx, ndx, nikkei, kospi):
                if x and x.get("lastUpdate"):
                    last = x["lastUpdate"]
            self.overseas = {**base, **extras, "lastUpdate": last or base.get("lastUpdate")}

    @staticmethod
    def _prev_trade_date(d: date | None = None) -> date:
        """简单跳过周末；法定节假日未单独处理。"""
        x = (d or date.today()) - timedelta(days=1)
        while x.weekday() >= 5:
            x -= timedelta(days=1)
        return x

    @staticmethod
    def _em_pool_full_code(item: dict) -> str | None:
        c = str(item.get("c") or "").zfill(6)
        if not c.isdigit() or len(c) != 6:
            return None
        m = item.get("m")
        if m == 1 or (m is None and c.startswith(("5", "6", "9"))):
            return f"sh{c}"
        return f"sz{c}"

    @staticmethod
    def _em_pool_days(item: dict) -> int:
        days = int(((item.get("zttj") or {}).get("days")) or item.get("lbc") or 1)
        return max(1, days)

    async def _fetch_limit_up_pool(
        self,
        client: httpx.AsyncClient,
        pool_type: str,
        pagesize: int,
        *,
        trade_date: date | None = None,
    ) -> dict:
        d = trade_date or date.today()
        date_str = f"{d.year}{d.month:02d}{d.day:02d}"
        url = (
            f"https://push2ex.eastmoney.com/getTopic{pool_type}Pool"
            f"?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
            f"&Pageindex=0&pagesize={pagesize}&sort=fbt%3Aasc&date={date_str}"
        )
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
            j = r.json()
            data = j.get("data") or {}
            return {"tc": data.get("tc") or 0, "pool": data.get("pool") or [], "date": date_str}
        except Exception:
            return {"tc": 0, "pool": [], "date": date_str}

    async def _quotes_change_map(self, client: httpx.AsyncClient, codes: list[str]) -> dict[str, float]:
        """批量取今日涨跌幅%（腾讯行情）。"""
        out: dict[str, float] = {}
        uniq = [c for c in dict.fromkeys(codes) if c]
        for i in range(0, len(uniq), 60):
            batch = uniq[i:i + 60]
            got = await self._fetch_quotes_batch(client, batch)
            for code, q in got.items():
                try:
                    out[code] = float(q.get("changePct") or 0.0)
                except (TypeError, ValueError):
                    continue
        return out

    async def _fetch_limit_up_stats(self, client: httpx.AsyncClient) -> None:
        try:
            yday = self._prev_trade_date()
            zt, zb, dt, yzt = await asyncio.gather(
                self._fetch_limit_up_pool(client, "ZT", 200),
                self._fetch_limit_up_pool(client, "ZB", 50),
                self._fetch_limit_up_pool(client, "DT", 1),
                self._fetch_limit_up_pool(client, "ZT", 200, trade_date=yday),
            )
            max_days = 0
            sector_count: dict[str, int] = {}
            ladder: dict[str, int] = {}
            today_by_code: dict[str, dict] = {}
            for s in zt.get("pool") or []:
                days = self._em_pool_days(s)
                if days > max_days:
                    max_days = days
                key = "5+" if days >= 5 else str(days)
                ladder[key] = ladder.get(key, 0) + 1
                hb = s.get("hybk") or "其他"
                sector_count[hb] = sector_count.get(hb, 0) + 1
                full = self._em_pool_full_code(s)
                if full:
                    today_by_code[full] = {"days": days, "raw": s}

            top_sector = ""
            for k, v in sector_count.items():
                if not top_sector or v > sector_count[top_sector]:
                    top_sector = k

            zt_n = int(zt.get("tc") or 0)
            zb_n = int(zb.get("tc") or 0)
            dt_n = int(dt.get("tc") or 0)
            break_rate = None
            if zt_n + zb_n > 0:
                break_rate = round(zb_n / (zt_n + zb_n) * 100, 1)

            # 昨涨停今表现 / 连板晋级 / 大幅回撤
            yest_items: list[tuple[str, int]] = []
            for s in yzt.get("pool") or []:
                full = self._em_pool_full_code(s)
                if not full:
                    continue
                yest_items.append((full, self._em_pool_days(s)))

            yest_premium = None
            yest_sample = 0
            promote_eligible = 0
            promote_success = 0
            promote_rate = None
            big_drawdown = 0
            yest_loss = 0
            drawdown_thr = -5.0

            if yest_items:
                chg_map = await self._quotes_change_map(client, [c for c, _ in yest_items])
                chgs: list[float] = []
                for code, ydays in yest_items:
                    chg = chg_map.get(code)
                    if chg is None:
                        continue
                    chgs.append(chg)
                    if chg < 0:
                        yest_loss += 1
                    if chg <= drawdown_thr:
                        big_drawdown += 1
                    # 昨日 N 板 → 今日仍涨停且天数 ≥ N+1，计为晋级
                    promote_eligible += 1
                    today = today_by_code.get(code)
                    if today and int(today["days"]) >= ydays + 1:
                        promote_success += 1
                yest_sample = len(chgs)
                if chgs:
                    yest_premium = round(sum(chgs) / len(chgs), 2)
                if promote_eligible > 0:
                    promote_rate = round(promote_success / promote_eligible * 100, 1)

            self.limit_up_stats = {
                "zt": zt_n,
                "zb": zb_n,
                "dt": dt_n,
                "maxDays": max_days,
                "topSector": top_sector,
                "ladder": ladder,
                "breakRate": break_rate,
                "yestPremium": yest_premium,
                "yestPremiumSample": yest_sample,
                "promoteRate": promote_rate,
                "promoteEligible": promote_eligible,
                "promoteSuccess": promote_success,
                "bigDrawdown": big_drawdown,
                "bigDrawdownThr": drawdown_thr,
                "yestLoss": yest_loss,
                "yestDate": yzt.get("date"),
                "source": "东方财富",
                "lastUpdate": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

    def _sector_delta(self, sector_code: str, net_inflow: float, now: datetime, minutes: int) -> float | None:
        """相对约 N 分钟前净流入变化（亿元）。历史不足时返回 None。"""
        if minutes <= 0:
            return 0.0
        if not self._sector_flow_history:
            return None
        target = now.timestamp() - minutes * 60
        # 至少要有接近目标时刻的快照（允许 ±40% 窗口），否则视为样本不足
        window = minutes * 60 * 0.4
        chosen: dict[str, float] | None = None
        best_gap = float("inf")
        for ts, snap in self._sector_flow_history:
            gap = abs(ts.timestamp() - target)
            if gap < best_gap:
                best_gap = gap
                chosen = snap
        if not chosen or best_gap > window:
            return None
        prev = chosen.get(sector_code)
        if prev is None:
            return None
        return round((net_inflow - prev) / 1e8, 2)

    def _sector_series(
        self,
        sector_code: str,
        current_yuan: float,
        now: datetime,
        *,
        max_points: int = 36,
    ) -> list[dict[str, Any]]:
        """盘中累计净流入曲线采样（亿元）。"""
        pts: list[dict[str, Any]] = []
        for ts, snap in self._sector_flow_history:
            if sector_code not in snap:
                continue
            pts.append({
                "t": ts.isoformat(),
                "v": round(float(snap[sector_code]) / 1e8, 2),
            })
        pts.append({
            "t": now.isoformat(),
            "v": round(current_yuan / 1e8, 2),
        })
        if len(pts) <= max_points:
            return pts
        # 均匀抽稀，保留首尾
        out = [pts[0]]
        step = (len(pts) - 1) / (max_points - 1)
        for i in range(1, max_points - 1):
            out.append(pts[int(round(i * step))])
        out.append(pts[-1])
        return out

    async def _request_sector_flow_page(self, client: httpx.AsyncClient, *, po: int, pz: int) -> list[dict]:
        query = (
            f"?pn=1&pz={pz}&po={po}&np=1&fltt=2&fid=f62&fs=m:90+t:2"
            "&fields=f12,f14,f2,f3,f62,f184,f66,f69,f267,f268"
            "&ut=fa5fd1943c7b386f172d6893dbfba10b"
        )
        urls = [
            "https://push2.eastmoney.com/api/qt/clist/get" + query,
            "https://push2delay.eastmoney.com/api/qt/clist/get" + query,
        ]
        for url in urls:
            for trust_env in (True, False):
                try:
                    if trust_env:
                        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
                    else:
                        async with httpx.AsyncClient(trust_env=False) as raw_client:
                            r = await raw_client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
                    j = r.json()
                    diff = (j.get("data") or {}).get("diff")
                    if isinstance(diff, dict):
                        return list(diff.values())
                    if isinstance(diff, list) and diff:
                        return diff
                except Exception:
                    continue
        return []

    async def _fetch_sector_flow(self, client: httpx.AsyncClient) -> None:
        try:
            # po=1: inflow desc; po=0: outflow first (most negative).
            inflow_raw, outflow_raw = await asyncio.gather(
                self._request_sector_flow_page(client, po=1, pz=40),
                self._request_sector_flow_page(client, po=0, pz=40),
            )
            merged: dict[str, dict] = {}
            for d in inflow_raw + outflow_raw:
                code = str(d.get("f12") or "")
                if code:
                    merged[code] = d
            diffs = list(merged.values())
            if not diffs:
                return

            now = datetime.now(timezone.utc)
            snapshot: dict[str, float] = {}
            rows: list[dict[str, Any]] = []
            for d in diffs:
                code = str(d.get("f12") or "")
                name = str(d.get("f14") or "")
                net_inflow = float(d.get("f62") or 0.0)  # yuan
                if not code or not name:
                    continue
                snapshot[code] = net_inflow
                net_inflow_e = round(net_inflow / 1e8, 2)
                delta5 = self._sector_delta(code, net_inflow, now, 5)
                delta15 = self._sector_delta(code, net_inflow, now, 15)
                delta30 = self._sector_delta(code, net_inflow, now, 30)
                d5 = 0.0 if delta5 is None else delta5
                change_pct = round(float(d.get("f3") or 0.0), 2)
                strength = round(float(d.get("f184") or 0.0), 2)  # 净流入率%
                leader_in = round(float(d.get("f66") or 0.0) / 1e8, 2)
                leader_out = round(float(d.get("f69") or 0.0) / 1e8, 2)
                series = self._sector_series(code, net_inflow, now)

                # 节奏：相对约 5 分钟前净流入变化（非叙事性标签）
                if net_inflow_e > 0 and d5 > 0.05:
                    pace = "in_accel"
                elif net_inflow_e > 0 and d5 < -0.05:
                    pace = "in_decel"
                elif net_inflow_e > 0:
                    pace = "in_hold"
                elif net_inflow_e < 0 and d5 < -0.05:
                    pace = "out_accel"
                elif net_inflow_e < 0 and d5 > 0.05:
                    pace = "out_decel"
                elif net_inflow_e < 0:
                    pace = "out_hold"
                else:
                    pace = "flat"

                # 价资背离：涨跌与主力净流入方向相反
                divergence = None
                if change_pct >= 0.5 and net_inflow_e < -0.3:
                    divergence = "price_up_flow_out"
                elif change_pct <= -0.5 and net_inflow_e > 0.3:
                    divergence = "price_down_flow_in"

                trend = "up" if d5 > 0 else ("down" if d5 < 0 else "flat")
                rows.append({
                    "sectorCode": code,
                    "sectorName": name,
                    "netInflow": net_inflow_e,
                    "delta5m": delta5,
                    "delta15m": delta15,
                    "delta30m": delta30,
                    "series": series,
                    "trend": trend,
                    "pace": pace,
                    "strength": strength,
                    "changePct": change_pct,
                    "leaderInflow": leader_in,
                    "leaderOutflow": leader_out,
                    "divergence": divergence,
                    "rankTag": "",
                })

            rows.sort(key=lambda x: x["netInflow"], reverse=True)
            for idx, row in enumerate(rows):
                if idx < 3 and row["netInflow"] > 0:
                    row["rankTag"] = "top"
                elif row.get("divergence"):
                    row["rankTag"] = "diverge"
                elif row["netInflow"] > 0 and row["pace"] == "in_accel":
                    row["rankTag"] = "hot"
                elif row["netInflow"] < 0:
                    row["rankTag"] = "cold"
                else:
                    row["rankTag"] = "normal"

            self._sector_flow_history.append((now, snapshot))
            cutoff = now.timestamp() - 5400
            self._sector_flow_history = [
                (ts, snap) for ts, snap in self._sector_flow_history if ts.timestamp() >= cutoff
            ]

            inflow_rows = [r for r in rows if r["netInflow"] > 0]
            outflow_rows = [r for r in rows if r["netInflow"] < 0]
            by_strength = sorted(rows, key=lambda x: x.get("strength") or 0, reverse=True)
            top = inflow_rows[0] if inflow_rows else (rows[0] if rows else None)
            bottom = min(outflow_rows, key=lambda x: x["netInflow"]) if outflow_rows else None
            top_str = by_strength[0] if by_strength else None
            diverge_n = sum(1 for r in rows if r.get("divergence"))
            hist_minutes = 0
            if self._sector_flow_history:
                oldest = self._sector_flow_history[0][0]
                hist_minutes = max(0, int((now.timestamp() - oldest.timestamp()) / 60))
            self.sector_flow_cache = {
                "summary": {
                    "totalNetInflow": round(sum(r["netInflow"] for r in rows), 2),
                    "positiveCount": len(inflow_rows),
                    "negativeCount": len(outflow_rows),
                    "total": len(rows),
                    "divergenceCount": diverge_n,
                    "historyMinutes": hist_minutes,
                    "historyPoints": len(self._sector_flow_history),
                    "topSector": top["sectorName"] if top else None,
                    "topNetInflow": top["netInflow"] if top else 0,
                    "topChangePct": top["changePct"] if top else 0,
                    "topStrengthSector": top_str["sectorName"] if top_str else None,
                    "topStrength": top_str["strength"] if top_str else 0,
                    "bottomSector": bottom["sectorName"] if bottom else None,
                    "bottomNetInflow": bottom["netInflow"] if bottom else 0,
                    "bottomChangePct": bottom["changePct"] if bottom else 0,
                },
                "list": rows,
                "source": "东方财富·主力净流入估算",
                "disclaimer": (
                    "主力净流入为券商席位估算口径，非交易所官方资金；"
                    "净流入率=净流入/成交额，更反映资金浓度。"
                    "5/15/30 分钟变化与曲线依赖本机轮询历史，重启后需积累一段时间。"
                ),
                "lastUpdate": now.isoformat(),
            }
        except Exception:
            pass

    async def fetch_kline(self, code: str) -> dict:
        param = f"{code},day,,,60,qfq"
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
        empty = {
            "code": code, "sparkline": [], "ma20": 0, "ma60": 0,
            "change20d": 0, "change60d": 0, "avgVol5": 0, "maxHigh60": 0, "klines": [],
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, timeout=8.0, follow_redirects=True)
                j = r.json()
            data = (j.get("data") or {}).get(code) or {}
            klines = data.get("qfqday") or data.get("day") or []
            if not klines:
                return empty
            closes = [float(k[2]) for k in klines]
            last20 = closes[-20:]
            last60 = closes[-60:]
            ma20 = sum(last20) / len(last20) if last20 else 0
            ma60 = sum(last60) / len(last60) if last60 else 0
            p20 = closes[-20] if len(closes) >= 20 else closes[0]
            p60 = closes[-60] if len(closes) >= 60 else closes[0]
            change20d = ((closes[-1] - p20) / p20 * 100) if p20 else 0
            change60d = ((closes[-1] - p60) / p60 * 100) if p60 else 0
            last5 = klines[-5:]
            avg_vol5 = sum(float(k[5]) for k in last5) / len(last5) if last5 else 0
            max_high = max(float(k[3]) for k in klines[-60:]) if klines else 0
            return {
                "code": code,
                "sparkline": [round(x, 2) for x in closes[-10:]],
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
                "change20d": round(change20d, 2),
                "change60d": round(change60d, 2),
                "avgVol5": round(avg_vol5),
                "maxHigh60": round(max_high, 2),
                "klines": [
                    {
                        "date": k[0],
                        "open": float(k[1]),
                        "close": float(k[2]),
                        "high": float(k[3]),
                        "low": float(k[4]),
                        "volume": float(k[5]),
                    }
                    for k in klines[-90:]
                ],
            }
        except Exception:
            return empty

    async def fetch_all_klines(self) -> None:
        if self._fetching_k:
            return
        self._fetching_k = True
        try:
            codes = list(dict.fromkeys([*self.stock_codes, *INDEX_CODES]))
            results = await asyncio.gather(*[self.fetch_kline(c) for c in codes])
            for r in results:
                if r.get("sparkline") or r.get("ma20"):
                    self.kline_cache[r["code"]] = r
            active = set(codes)
            for c in list(self.kline_cache.keys()):
                if c not in active:
                    del self.kline_cache[c]
            self.last_kline_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching_k = False

    @staticmethod
    def pe_hard_max(*, group: str | None = None, tech: bool | None = None) -> float:
        from app.domain.sectors import valuation_profile
        if group is None and tech is not None:
            group = "tech" if tech else "default"
        return float(valuation_profile(group or "default")["hard_max"])

    @staticmethod
    def pe_composite_points(pe: float, *, group: str | None = None, tech: bool | None = None) -> int:
        """综合分 PE 项（满分 25）。按估值族分档。"""
        from app.domain.sectors import valuation_profile
        if group is None and tech is not None:
            group = "tech" if tech else "default"
        p = valuation_profile(group or "default")
        n = float(pe or 0)
        if not (n > 0):
            return int(p.get("loss_pts") or 0)
        for upper, pts in p.get("bands") or ():
            if n < float(upper):
                return int(pts)
        return 0

    @staticmethod
    def pe_soft_points(pe: float, *, full: int = 15, group: str | None = None, tech: bool | None = None) -> int:
        """策略内 PE 软分。"""
        from app.domain.sectors import valuation_profile
        if group is None and tech is not None:
            group = "tech" if tech else "default"
        p = valuation_profile(group or "default")
        n = float(pe or 0)
        if not (n > 0):
            return max(0, round(full * float(p.get("soft_loss") or 0)))
        for upper, ratio in p.get("soft_bands") or ():
            if n < float(upper):
                return max(1, round(full * float(ratio)))
        return 0

    @staticmethod
    def _val_group_from_q(q: dict) -> str:
        from app.domain.sectors import valuation_group

        return valuation_group(
            str(q.get("code") or ""),
            sector=q.get("sector"),
            industry=q.get("industry") or q.get("hybk"),
        )

    @staticmethod
    def _tech_from_q(q: dict) -> bool:
        return MarketService._val_group_from_q(q) == "tech"

    @staticmethod
    def final_score(q: dict, k: dict) -> int:
        s = 0
        pe = q.get("peTTM") or q.get("pe") or 0
        group = MarketService._val_group_from_q(q)
        s += MarketService.pe_composite_points(pe, group=group)
        ma20 = k.get("ma20") or 0
        price = q.get("price") or 0
        if ma20 > 0 and price > 0:
            dist = (price - ma20) / ma20 * 100
            if dist >= 0:
                s += 25
            elif dist > -3:
                s += 20
            elif dist > -5:
                s += 15
            elif dist > -10:
                s += 5
        c20 = k.get("change20d") or 0
        if c20 > 5:
            s += 20
        elif c20 > 0:
            s += 15
        elif c20 > -5:
            s += 10
        elif c20 > -10:
            s += 5
        lb = q.get("liangbi") or 0
        if lb > 2:
            s += 15
        elif lb > 1.5:
            s += 12
        elif lb > 1:
            s += 8
        else:
            s += 5
        wb = q.get("weibi") or 0
        if wb > 30:
            s += 15
        elif wb > 10:
            s += 12
        elif wb > 0:
            s += 8
        elif wb > -20:
            s += 5
        return s

    @staticmethod
    def score_quote(q: dict) -> int:
        s = 0
        pe = q.get("peTTM") or 0
        group = MarketService._val_group_from_q(q)
        s += MarketService.pe_composite_points(pe, group=group)
        wb = q.get("weibi") or 0
        if wb > 30:
            s += 15
        elif wb > 10:
            s += 10
        elif wb > 0:
            s += 5
        lb = q.get("liangbi") or 0
        if lb > 2:
            s += 15
        elif lb > 1.5:
            s += 10
        elif lb > 1:
            s += 5
        chg = q.get("changePct") or 0
        if 0 < chg < 7:
            s += 10
        pb = q.get("pb") or 0
        if 0 < pb < 3:
            s += 10
        elif 0 < pb < 5:
            s += 8
        return s

    @staticmethod
    def build_signals(q: dict, k: dict) -> list[str]:
        signals: list[str] = []
        ma20 = k.get("ma20") or 0
        price = q.get("price") or 0
        if ma20 > 0 and price >= ma20:
            signals.append("站上20日线")
        if ma20 > 0 and price < ma20:
            signals.append("破20日线")
        wb = q.get("weibi") or 0
        if wb > 30:
            signals.append(f"委比强势+{wb:.0f}%")
        lb = q.get("liangbi") or 0
        if lb > 2:
            signals.append(f"放量(量比{lb:.1f})")
        pe = q.get("peTTM") or 0
        if 0 < pe < 40:
            signals.append(f"低PE({pe:.0f})")
        elif 0 < pe < 80:
            signals.append(f"估值尚可({pe:.0f})")
        c20 = k.get("change20d") or 0
        if c20 > 0:
            signals.append(f"20日+{c20:.1f}%")
        if c20 < -15:
            signals.append(f"超跌({c20:.1f}%)")
        return signals

    @staticmethod
    def auction_score(q: dict) -> dict:
        s = 0
        signals: list[str] = []
        gap = q.get("changePct") or 0
        if 3 <= gap <= 7:
            s += 30
            signals.append(f"高开+{gap:.1f}%")
        elif 7 < gap <= 10:
            s += 25
            signals.append(f"大幅高开+{gap:.1f}%")
        elif 1 < gap < 3:
            s += 20
            signals.append(f"温和高开+{gap:.1f}%")
        elif gap > 10:
            s += 15
            signals.append(f"涨停附近+{gap:.1f}%")
        elif gap >= 0:
            s += 5
        wb = q.get("weibi") or 0
        if wb > 50:
            s += 25
            signals.append(f"委比极强+{wb:.0f}%")
        elif wb > 30:
            s += 20
            signals.append(f"委比强势+{wb:.0f}%")
        elif wb > 10:
            s += 15
            signals.append(f"委比正向+{wb:.0f}%")
        elif wb > 0:
            s += 10
        lb = q.get("liangbi") or 0
        if lb > 3:
            s += 20
            signals.append(f"巨量(量比{lb:.1f})")
        elif lb > 2:
            s += 15
            signals.append(f"放量(量比{lb:.1f})")
        elif lb > 1.5:
            s += 10
        elif lb > 1:
            s += 5
        pe = q.get("peTTM") or q.get("pe") or 0
        group = MarketService._val_group_from_q(q)
        pts = MarketService.pe_composite_points(pe, group=group)
        s += pts
        if group == "tech" and 0 < pe < 50:
            signals.append(f"科技估值尚可({pe:.0f})")
        elif group == "cyclical" and 0 < pe < 20:
            signals.append(f"周期低估({pe:.0f})")
        elif 0 < pe < 40:
            signals.append(f"低PE({pe:.0f})")
        elif 0 < pe < 80:
            signals.append(f"估值尚可({pe:.0f})")
        return {
            "code": q.get("code"),
            "name": q.get("name"),
            "price": q.get("price"),
            "changePct": q.get("changePct"),
            "open": q.get("open"),
            "weibi": q.get("weibi"),
            "liangbi": q.get("liangbi"),
            "pe": pe,
            "pb": q.get("pb") or 0,
            "score": s,
            "signals": signals,
        }

    @staticmethod
    def trend_swing_score(q: dict, k: dict) -> dict | None:
        """趋势波段 L1 分（对齐 knowledge/趋势波段策略.md）；不达标返回 None。"""
        price = float(q.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if price <= 0 or ma20 <= 0 or price < ma20:
            return None
        c20 = float(k.get("change20d") or 0)
        if c20 <= 0 or c20 > 60:
            return None
        pe = float(q.get("peTTM") or q.get("pe") or 0)
        group = MarketService._val_group_from_q(q)
        if pe > MarketService.pe_hard_max(group=group):
            return None

        tags: list[str] = ["站上20日线"]
        s = 0.0

        dist = (price - ma20) / ma20 * 100
        if 0 <= dist <= 8:
            s += 25
            tags.append("贴近20日线")
        elif dist <= 15:
            s += 18
        elif dist <= 25:
            s += 10
            tags.append("偏离偏大")
        else:
            s += 4
            tags.append("远离20日线")

        if 5 < c20 <= 35:
            s += 25
            tags.append("趋势走强")
        elif 0 < c20 <= 5:
            s += 15
        else:  # 35 < c20 <= 60
            s += 12
            tags.append("涨幅已大")

        lb = float(q.get("liangbi") or 0)
        chg = float(q.get("changePct") or 0)
        if 1.05 <= lb <= 2.0 and chg < 7:
            s += 20
            tags.append("温和放量")
        elif lb > 2 and chg < 5:
            s += 12
            tags.append("放量")
        elif lb > 1:
            s += 8
        else:
            s += 4

        if 0 <= chg < 5:
            s += 15
        elif 5 <= chg < 7:
            s += 10
        elif chg >= 7:
            s += 2
            tags.append("当日涨幅偏大")
        else:
            s += 6

        s += MarketService.pe_soft_points(pe, full=15, group=group)

        return {
            "trendScore": int(round(min(100.0, s))),
            "trendTags": tags[:6],
            "distMa20Pct": round(dist, 2),
            "why": tags[:5],
        }

    @staticmethod
    def pullback_score(q: dict, k: dict) -> dict | None:
        """趋势回踩 L1（对齐 knowledge/趋势回踩策略.md）。"""
        price = float(q.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        ma60 = float(k.get("ma60") or 0)
        if price <= 0 or ma20 <= 0 or price < ma20:
            return None
        if ma60 > 0 and price < ma60:
            return None
        c20 = float(k.get("change20d") or 0)
        if c20 <= 0 or c20 > 45:
            return None
        dist = (price - ma20) / ma20 * 100
        if dist < -1.5 or dist > 6:
            return None
        chg = float(q.get("changePct") or 0)
        if chg < -3 or chg > 3:
            return None
        lb = float(q.get("liangbi") or 0)
        vol = float(q.get("volume") or 0)
        avg5 = float(k.get("avgVol5") or 0)
        shrink = (0 < lb <= 1.6) or (avg5 > 0 and vol > 0 and vol <= avg5 * 1.05)
        if not shrink:
            return None
        pe = float(q.get("peTTM") or q.get("pe") or 0)
        group = MarketService._val_group_from_q(q)
        if pe > MarketService.pe_hard_max(group=group):
            return None

        tags: list[str] = ["回踩MA20", "趋势未坏"]
        why: list[str] = [f"距MA20 {dist:+.1f}%", f"20日 {c20:+.1f}%"]
        s = 0.0

        if 0 <= dist <= 4:
            s += 30
            tags.append("贴近回踩带")
        elif dist <= 6:
            s += 20
        else:
            s += 12

        if 5 < c20 <= 30:
            s += 25
        elif 0 < c20 <= 5:
            s += 15
        else:
            s += 10
            tags.append("涨幅已不小")

        if 0 < lb <= 0.9:
            s += 25
            tags.append("缩量")
            why.append(f"量比 {lb:.2f} 缩量")
        elif lb <= 1.3:
            s += 18
            tags.append("量能温和")
            why.append(f"量比 {lb:.2f}")
        elif lb <= 1.6:
            s += 10
            why.append(f"量比 {lb:.2f}")
        else:
            s += 6
            tags.append("量比偏高")
            why.append(f"量比 {lb:.2f} 偏高")

        if abs(chg) <= 1:
            s += 10
            why.append(f"当日 {chg:+.1f}% 克制")
        elif abs(chg) <= 3:
            s += 6
            why.append(f"当日 {chg:+.1f}%")
        else:
            s += 2

        s += MarketService.pe_soft_points(pe, full=10, group=group)

        if ma60 > 0:
            why.append("站上MA60")

        return {
            "pullbackScore": int(round(min(100.0, s))),
            "pullbackTags": tags[:6],
            "distMa20Pct": round(dist, 2),
            "why": why[:6],
        }

    def flow_resonance_score(
        self,
        q: dict,
        k: dict,
        *,
        focus_names: list[str],
        focus_rank: dict[str, int],
    ) -> dict | None:
        """资金共振 L1（对齐 knowledge/资金共振策略.md）。"""
        from app.domain.sectors import get_sector, match_focus_sector

        code = str(q.get("code") or "")
        hit = match_focus_sector(code, focus_names)
        if not hit:
            return None
        price = float(q.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if price <= 0 or ma20 <= 0 or price < ma20:
            return None
        c20 = float(k.get("change20d") or 0)
        if c20 <= 0 or c20 > 50:
            return None
        chg = float(q.get("changePct") or 0)
        if chg >= 7:
            return None
        pe = float(q.get("peTTM") or q.get("pe") or 0)
        group = MarketService._val_group_from_q(q)
        if pe > MarketService.pe_hard_max(group=group):
            return None

        rank = int(focus_rank.get(hit) or 99)
        tags = [f"对齐{hit}", "站上20日线"]
        why = [f"板块资金强度≈Top{rank}（{hit}）", f"Jarvis板块 {get_sector(code)}"]
        s = 0.0
        # 位次分：Top1=35 … Top8≈8
        s += max(8.0, 35.0 - (rank - 1) * 4.0)

        dist = (price - ma20) / ma20 * 100
        if 0 <= dist <= 10:
            s += 25
            why.append(f"距MA20 {dist:+.1f}%")
        elif dist <= 20:
            s += 15
            tags.append("偏离偏大")
            why.append(f"距MA20 {dist:+.1f}% 偏大")
        else:
            s += 6
            tags.append("远离20日线")

        if 5 < c20 <= 35:
            s += 20
            tags.append("趋势走强")
            why.append(f"20日 {c20:+.1f}%")
        elif c20 <= 5:
            s += 12
            why.append(f"20日 {c20:+.1f}%")
        else:
            s += 8
            tags.append("涨幅已大")
            why.append(f"20日 {c20:+.1f}% 已大")

        lb = float(q.get("liangbi") or 0)
        if 1.05 <= lb <= 2.0:
            s += 10
            why.append(f"量比 {lb:.2f} 温和")
        elif lb > 2:
            s += 5
            tags.append("放量")
        else:
            s += 4

        s += MarketService.pe_soft_points(pe, full=10, group=group)

        if chg >= 5:
            tags.append("当日涨幅偏大")
            why.append(f"当日 {chg:+.1f}% 慎追")

        return {
            "flowScore": int(round(min(100.0, s))),
            "flowTags": tags[:6],
            "focusSector": hit,
            "focusRank": rank,
            "distMa20Pct": round(dist, 2),
            "why": why[:6],
        }

    async def screen_top(self) -> dict:
        from app.domain.sectors import get_sector, valuation_group

        batches = [SCREEN_UNIVERSE[i : i + 40] for i in range(0, len(SCREEN_UNIVERSE), 40)]
        async with httpx.AsyncClient() as client:
            batch_results = await asyncio.gather(*[self._fetch_quotes_batch(client, b) for b in batches])
        all_quotes: dict[str, dict] = {}
        for b in batch_results:
            all_quotes.update(b)

        try:
            await self.ensure_industries(list(all_quotes.keys()))
        except Exception:
            pass

        candidates = []
        for code, q in all_quotes.items():
            if not q or (q.get("price") or 0) <= 0:
                continue
            pe = q.get("peTTM") or 0
            q = dict(q)
            q["code"] = code
            ind = self.industry_of(code)
            if ind:
                q["industry"] = ind
            group = valuation_group(code, industry=ind or None)
            if pe > MarketService.pe_hard_max(group=group):
                continue
            candidates.append({"code": code, "quote": q})

        # 全候选拉 K，供多策略共用（宇宙约 80）
        kline_results = await asyncio.gather(*[self.fetch_kline(c["code"]) for c in candidates])
        kline_map = {k["code"]: k for k in kline_results if k.get("code")}

        sf_list = list((self.sector_flow_cache or {}).get("list") or [])
        by_strength = sorted(
            [r for r in sf_list if r.get("sectorName") and (r.get("strength") or r.get("netInflow"))],
            key=lambda r: float(r.get("strength") or 0),
            reverse=True,
        )
        focus_rows = by_strength[:8]
        focus_names = [str(r.get("sectorName")) for r in focus_rows]
        focus_rank = {str(r.get("sectorName")): i + 1 for i, r in enumerate(focus_rows)}

        scored = []
        trend_scored = []
        pullback_scored = []
        flow_scored = []
        for c in candidates:
            q = c["quote"]
            k = kline_map.get(c["code"]) or {}
            row = {
                "code": c["code"],
                "name": q.get("name"),
                "price": q.get("price"),
                "changePct": q.get("changePct"),
                "pe": q.get("peTTM") or q.get("pe") or 0,
                "pb": q.get("pb") or 0,
                "weibi": q.get("weibi") or 0,
                "liangbi": q.get("liangbi") or 0,
                "ma20": k.get("ma20") or 0,
                "ma60": k.get("ma60") or 0,
                "aboveMA20": bool(k.get("ma20") and q.get("price") and q["price"] >= k["ma20"]),
                "change20d": k.get("change20d") or 0,
                "change60d": k.get("change60d") or 0,
                "avgVol5": k.get("avgVol5") or 0,
                "score": self.final_score(q, k),
                "signals": self.build_signals(q, k),
                "sector": get_sector(c["code"]),
                "industry": q.get("industry") or self.industry_of(c["code"]) or "",
            }
            # 综合质量 why
            why_q = []
            if row["aboveMA20"]:
                why_q.append("站上MA20")
            else:
                why_q.append("破MA20或不足")
            why_q.append(f"综合分 {row['score']}")
            if row.get("change20d"):
                why_q.append(f"20日 {float(row['change20d']):+.1f}%")
            if row.get("liangbi"):
                why_q.append(f"量比 {float(row['liangbi']):.2f}")
            row["why"] = why_q[:5]
            scored.append(row)

            tr = self.trend_swing_score(q, k)
            if tr:
                trow = dict(row)
                trow["trendScore"] = tr["trendScore"]
                trow["trendTags"] = tr["trendTags"]
                trow["distMa20Pct"] = tr["distMa20Pct"]
                trow["why"] = list(tr.get("why") or tr.get("trendTags") or [])[:6]
                extra = [t for t in tr["trendTags"] if t not in (trow.get("signals") or [])]
                trow["signals"] = list(trow.get("signals") or []) + extra
                trend_scored.append(trow)

            pb = self.pullback_score(q, k)
            if pb:
                prow = dict(row)
                prow["pullbackScore"] = pb["pullbackScore"]
                prow["pullbackTags"] = pb["pullbackTags"]
                prow["distMa20Pct"] = pb["distMa20Pct"]
                prow["why"] = pb.get("why") or pb.get("pullbackTags") or []
                extra = [t for t in pb["pullbackTags"] if t not in (prow.get("signals") or [])]
                prow["signals"] = list(prow.get("signals") or []) + extra
                pullback_scored.append(prow)

            fr = self.flow_resonance_score(q, k, focus_names=focus_names, focus_rank=focus_rank)
            if fr:
                frow = dict(row)
                frow["flowScore"] = fr["flowScore"]
                frow["flowTags"] = fr["flowTags"]
                frow["focusSector"] = fr["focusSector"]
                frow["focusRank"] = fr["focusRank"]
                frow["distMa20Pct"] = fr["distMa20Pct"]
                frow["why"] = fr.get("why") or []
                extra = [t for t in fr["flowTags"] if t not in (frow.get("signals") or [])]
                frow["signals"] = list(frow.get("signals") or []) + extra
                flow_scored.append(frow)

        scored.sort(key=lambda x: x["score"], reverse=True)
        trend_scored.sort(key=lambda x: x.get("trendScore") or 0, reverse=True)
        pullback_scored.sort(key=lambda x: x.get("pullbackScore") or 0, reverse=True)
        flow_scored.sort(key=lambda x: x.get("flowScore") or 0, reverse=True)
        return {
            "results": scored[:10],
            "trendResults": trend_scored[:5],
            "trendCandidates": len(trend_scored),
            "pullbackResults": pullback_scored[:5],
            "pullbackCandidates": len(pullback_scored),
            "flowResults": flow_scored[:5],
            "flowCandidates": len(flow_scored),
            "focusSectors": focus_names[:5],
            "universe": len(SCREEN_UNIVERSE),
            "scanned": len(all_quotes),
            "lastUpdate": datetime.now(timezone.utc).isoformat(),
        }

    async def auction_top(self) -> dict:
        extra = [c for c in self.stock_codes if c not in SCREEN_UNIVERSE]
        all_codes = SCREEN_UNIVERSE + extra
        batches = [all_codes[i : i + 40] for i in range(0, len(all_codes), 40)]
        async with httpx.AsyncClient() as client:
            batch_results = await asyncio.gather(*[self._fetch_quotes_batch(client, b) for b in batches])
        aquotes: dict[str, dict] = {}
        for b in batch_results:
            aquotes.update(b)

        scored = []
        for q in aquotes.values():
            if not q or (q.get("price") or 0) <= 0:
                continue
            item = self.auction_score(q)
            if item["score"] > 0:
                scored.append(item)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "results": scored[:10],
            "scanned": len(aquotes),
            "lastUpdate": datetime.now(timezone.utc).isoformat(),
        }


market = MarketService()
