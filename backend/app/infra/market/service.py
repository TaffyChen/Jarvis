from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.infra.storage import read_json, write_json

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
        self.sector_flow_cache = {
            "summary": {"totalNetInflow": 0.0, "positiveCount": 0, "total": 0, "topSector": None},
            "list": [],
            "source": "",
            "lastUpdate": None,
        }
        self._sector_flow_history: list[tuple[datetime, dict[str, float]]] = []
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
                await self._fetch_limit_up_stats(client)
                await self._fetch_sector_flow(client)
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

    async def _fetch_limit_up_pool(self, client: httpx.AsyncClient, pool_type: str, pagesize: int) -> dict:
        now = datetime.now()
        date_str = f"{now.year}{now.month:02d}{now.day:02d}"
        url = (
            f"https://push2ex.eastmoney.com/getTopic{pool_type}Pool"
            f"?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
            f"&Pageindex=0&pagesize={pagesize}&sort=fbt%3Aasc&date={date_str}"
        )
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
            j = r.json()
            data = j.get("data") or {}
            return {"tc": data.get("tc") or 0, "pool": data.get("pool") or []}
        except Exception:
            return {"tc": 0, "pool": []}

    async def _fetch_limit_up_stats(self, client: httpx.AsyncClient) -> None:
        try:
            zt, zb, dt = await asyncio.gather(
                self._fetch_limit_up_pool(client, "ZT", 200),
                self._fetch_limit_up_pool(client, "ZB", 1),
                self._fetch_limit_up_pool(client, "DT", 1),
            )
            max_days = 0
            sector_count: dict[str, int] = {}
            for s in zt.get("pool") or []:
                days = ((s.get("zttj") or {}).get("days")) or 1
                if days > max_days:
                    max_days = days
                hb = s.get("hybk") or "其他"
                sector_count[hb] = sector_count.get(hb, 0) + 1
            top_sector = ""
            for k, v in sector_count.items():
                if not top_sector or v > sector_count[top_sector]:
                    top_sector = k
            self.limit_up_stats = {
                "zt": zt.get("tc") or 0,
                "zb": zb.get("tc") or 0,
                "dt": dt.get("tc") or 0,
                "maxDays": max_days,
                "topSector": top_sector,
                "source": "东方财富",
                "lastUpdate": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

    def _sector_delta5(self, sector_code: str, net_inflow: float, now: datetime) -> float:
        # Pick the snapshot closest to 5 minutes ago. If unavailable, fallback to earliest snapshot.
        target = now.timestamp() - 300
        chosen: dict[str, float] | None = None
        best_gap = float("inf")
        for ts, snap in self._sector_flow_history:
            gap = abs(ts.timestamp() - target)
            if gap < best_gap:
                best_gap = gap
                chosen = snap
        if not chosen:
            return 0.0
        prev = chosen.get(sector_code, 0.0)
        return round((net_inflow - prev) / 1e8, 2)

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
                delta5 = self._sector_delta5(code, net_inflow, now)
                trend = "up" if delta5 > 0 else ("down" if delta5 < 0 else "flat")
                strength = float(d.get("f184") or 0.0)
                change_pct = round(float(d.get("f3") or 0.0), 2)
                leader_in = round(float(d.get("f66") or 0.0) / 1e8, 2)
                leader_out = round(float(d.get("f69") or 0.0) / 1e8, 2)
                rows.append({
                    "sectorCode": code,
                    "sectorName": name,
                    "netInflow": net_inflow_e,
                    "delta5m": delta5,
                    "trend": trend,
                    "strength": round(strength, 2),
                    "changePct": change_pct,
                    "leaderInflow": leader_in,
                    "leaderOutflow": leader_out,
                    "rankTag": "",
                })

            rows.sort(key=lambda x: x["netInflow"], reverse=True)
            for idx, row in enumerate(rows):
                if idx < 3:
                    row["rankTag"] = "top"
                elif row["netInflow"] > 0 and row["delta5m"] > 0:
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
            top = inflow_rows[0] if inflow_rows else (rows[0] if rows else None)
            bottom = min(outflow_rows, key=lambda x: x["netInflow"]) if outflow_rows else None
            self.sector_flow_cache = {
                "summary": {
                    "totalNetInflow": round(sum(r["netInflow"] for r in rows), 2),
                    "positiveCount": len(inflow_rows),
                    "negativeCount": len(outflow_rows),
                    "total": len(rows),
                    "topSector": top["sectorName"] if top else None,
                    "topNetInflow": top["netInflow"] if top else 0,
                    "topChangePct": top["changePct"] if top else 0,
                    "bottomSector": bottom["sectorName"] if bottom else None,
                    "bottomNetInflow": bottom["netInflow"] if bottom else 0,
                    "bottomChangePct": bottom["changePct"] if bottom else 0,
                },
                "list": rows,
                "source": "东方财富",
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

    @staticmethod
    def score_quote(q: dict) -> int:
        s = 0
        pe = q.get("peTTM") or 0
        if pe > 0 and pe < 30:
            s += 25
        elif pe > 0 and pe < 50:
            s += 20
        elif pe > 0 and pe < 80:
            s += 15
        elif pe > 0 and pe < 150:
            s += 10
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
        if 0 < pe < 30:
            signals.append(f"低PE({pe:.0f})")
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
        if 0 < pe < 30:
            s += 25
            signals.append(f"低PE({pe:.0f})")
        elif 0 < pe < 50:
            s += 20
        elif 0 < pe < 80:
            s += 15
        elif 0 < pe < 150:
            s += 10
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

    async def screen_top(self) -> dict:
        batches = [SCREEN_UNIVERSE[i : i + 40] for i in range(0, len(SCREEN_UNIVERSE), 40)]
        async with httpx.AsyncClient() as client:
            batch_results = await asyncio.gather(*[self._fetch_quotes_batch(client, b) for b in batches])
        all_quotes: dict[str, dict] = {}
        for b in batch_results:
            all_quotes.update(b)

        candidates = []
        for code, q in all_quotes.items():
            if not q or (q.get("price") or 0) <= 0:
                continue
            pe = q.get("peTTM") or 0
            if pe > 150:
                continue
            candidates.append({"code": code, "quote": q})
        candidates.sort(key=lambda c: self.score_quote(c["quote"]), reverse=True)
        top30 = candidates[:30]
        kline_results = await asyncio.gather(*[self.fetch_kline(c["code"]) for c in top30])
        kline_map = {k["code"]: k for k in kline_results if k.get("sparkline")}

        scored = []
        for c in top30:
            q = c["quote"]
            k = kline_map.get(c["code"]) or {}
            scored.append({
                "code": c["code"],
                "name": q.get("name"),
                "price": q.get("price"),
                "changePct": q.get("changePct"),
                "pe": q.get("peTTM") or q.get("pe") or 0,
                "pb": q.get("pb") or 0,
                "weibi": q.get("weibi") or 0,
                "liangbi": q.get("liangbi") or 0,
                "ma20": k.get("ma20") or 0,
                "aboveMA20": bool(k.get("ma20") and q.get("price") and q["price"] >= k["ma20"]),
                "change20d": k.get("change20d") or 0,
                "score": self.final_score(q, k),
                "signals": self.build_signals(q, k),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "results": scored[:10],
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
