from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.storage import read_json, write_json

INDEX_CODES = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300"]

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


def _load_codes() -> list[str]:
    codes = list(DEFAULT_CODES)
    extra = read_json("stock_codes.json", [])
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
            "zt": 0, "zb": 0, "dt": 0, "maxDays": 0, "topSector": "", "source": "", "lastUpdate": None
        }
        self.last_update: str | None = None
        self.last_kline_update: str | None = None
        self._fetching = False
        self._fetching_k = False

    def save_codes(self) -> None:
        write_json("stock_codes.json", self.stock_codes)

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
        if self._fetching:
            return
        self._fetching = True
        try:
            all_codes = self.stock_codes + INDEX_CODES
            batches = [all_codes[i : i + 20] for i in range(0, len(all_codes), 20)]
            async with httpx.AsyncClient() as client:
                results = await asyncio.gather(*[self._fetch_quotes_batch(client, b) for b in batches])
                await self._fetch_market_breadth(client)
                await self._fetch_overseas(client)
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
            self.last_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching = False

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
        url = (
            "https://push2delay.eastmoney.com/api/qt/stock/get"
            "?secid=100.SPX&fields=f43,f170&ut=fa5fd1943c7b386f172d6893dbfba10b"
        )
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8.0)
            d = (r.json().get("data") or {})
            if (d.get("f43") or 0) > 0:
                self.overseas = {
                    "code": "SPX",
                    "name": "标普500",
                    "price": round((d.get("f43") or 0) / 100, 2),
                    "changePct": (d.get("f170") or 0) / 100,
                    "lastUpdate": datetime.now(timezone.utc).isoformat(),
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
                    for k in klines[-60:]
                ],
            }
        except Exception:
            return empty

    async def fetch_all_klines(self) -> None:
        if self._fetching_k:
            return
        self._fetching_k = True
        try:
            results = await asyncio.gather(*[self.fetch_kline(c) for c in self.stock_codes])
            for r in results:
                if r.get("sparkline"):
                    self.kline_cache[r["code"]] = r
            active = set(self.stock_codes)
            for c in list(self.kline_cache.keys()):
                if c not in active:
                    del self.kline_cache[c]
            self.last_kline_update = datetime.now(timezone.utc).isoformat()
        finally:
            self._fetching_k = False

    @staticmethod
    def final_score(q: dict, k: dict) -> int:
        s = 0
        pe = q.get("peTTM") or q.get("pe") or 0
        if pe > 0 and pe < 30:
            s += 25
        elif pe > 0 and pe < 50:
            s += 20
        elif pe > 0 and pe < 80:
            s += 15
        elif pe > 0 and pe < 150:
            s += 10
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


market = MarketService()
