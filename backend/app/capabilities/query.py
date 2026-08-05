"""只读能力：行情 / 评分 / 知识 / 沉淀 / 持仓等。"""
from __future__ import annotations

from typing import Any

import re

import httpx

from app.capabilities.rag import retrieve_knowledge
from app.domain.codes import normalize_code
from app.domain.memory import search_memories as _search_memories
from app.infra.market.service import market
from app.infra.storage import read_json


def search_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve_knowledge(query or "", top_k=top_k)


def search_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    k = max(1, min(int(top_k or 5), 8))
    hits = _search_memories(query or "", top_k=k)
    return [
        {
            "id": h.get("id"),
            "kind": h.get("kind"),
            "code": h.get("code"),
            "title": h.get("title"),
            "content": h.get("content"),
            "score": h.get("_score"),
        }
        for h in hits
    ]


def get_quote(code: str) -> dict[str, Any]:
    c = normalize_code(code) or (code or "").strip().lower()
    q = market.quote_cache.get(c)
    if not q:
        return {"error": "unknown_or_no_quote", "code": c}
    keys = (
        "code",
        "name",
        "price",
        "changePct",
        "volume",
        "amount",
        "liangbi",
        "weibi",
        "peTTM",
        "pb",
        "high",
        "low",
        "open",
    )
    return {k: q.get(k) for k in keys}


def get_score(code: str) -> dict[str, Any]:
    c = normalize_code(code) or (code or "").strip().lower()
    q = market.quote_cache.get(c) or {}
    k = market.kline_cache.get(c) or {}
    if not q:
        return {"error": "no_quote", "code": c}
    score = market.final_score(q, k) if k else market.score_quote(q)
    return {
        "code": c,
        "name": q.get("name"),
        "score": score,
        "price": q.get("price"),
        "changePct": q.get("changePct"),
        "ma20": k.get("ma20"),
        "change20d": k.get("change20d"),
        "liangbi": q.get("liangbi"),
        "weibi": q.get("weibi"),
        "peTTM": q.get("peTTM"),
    }


def get_analysis(code: str) -> dict[str, Any]:
    c = normalize_code(code) or (code or "").strip().lower()
    a = (read_json("analyses.json", {}) or {}).get(c)
    if not a:
        return {"error": "no_analysis", "code": c}
    return {
        "code": c,
        "name": a.get("name"),
        "riskOk": a.get("riskOk"),
        "reviewedAt": a.get("reviewedAt"),
        "reason": a.get("reason"),
        "notes": a.get("notes"),
        "analysis": a.get("analysis"),
        "type": a.get("type"),
    }


def get_positions() -> list[dict[str, Any]]:
    positions = read_json("positions.json", {}) or {}
    if not isinstance(positions, dict):
        return []
    rows = []
    for code, p in positions.items():
        q = market.quote_cache.get(code) or {}
        rows.append(
            {
                "code": code,
                "buyPrice": p.get("buyPrice"),
                "shares": p.get("shares"),
                "price": q.get("price"),
                "changePct": q.get("changePct"),
                "name": q.get("name") or p.get("name"),
            }
        )
    return rows


def get_market_overview() -> dict[str, Any]:
    mb = market.market_breadth or {}
    ov = market.overseas or {}
    lu = getattr(market, "limit_up_stats", None) or {}
    return {
        "breadth": mb,
        "overseas": ov,
        "limitUp": {
            "today": (lu.get("today") if isinstance(lu, dict) else None),
            "summary": {
                k: lu.get(k)
                for k in ("upCount", "downCount", "limitUpCount")
                if isinstance(lu, dict)
            },
        },
    }


def _infer_type(code: str, name: str = "") -> str:
    if re.match(r"^(sh5|sz1)", code or ""):
        return "etf"
    if "ETF" in (name or "").upper() or "基金" in (name or ""):
        return "etf"
    return "stock"


def _local_code_hits(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    analyses = read_json("analyses.json", {}) or {}
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    pool: dict[str, dict[str, Any]] = {}
    for code, quote in (market.quote_cache or {}).items():
        pool[code] = {"code": code, "name": quote.get("name") or ""}
    if isinstance(analyses, dict):
        for code, row in analyses.items():
            prev = pool.get(code) or {"code": code, "name": ""}
            prev["name"] = prev["name"] or (row.get("name") or "")
            pool[code] = prev
    for code in market.stock_codes or []:
        pool.setdefault(code, {"code": code, "name": ""})

    for code, row in pool.items():
        name = str(row.get("name") or "")
        raw = code.replace("sh", "").replace("sz", "")
        blob = f"{code} {raw} {name}".lower()
        if q not in blob and q not in name:
            continue
        if code in seen:
            continue
        seen.add(code)
        hits.append({
            "code": code,
            "name": name or code,
            "type": _infer_type(code, name),
            "source": "local",
        })
        if len(hits) >= limit:
            break
    return hits


def _parse_tencent_hint(text: str) -> list[dict[str, Any]]:
    m = re.search(r'v_hint="([^"]*)"', text or "")
    if not m:
        return []
    rows = []
    for item in m.group(1).split("^"):
        parts = item.split("~")
        if len(parts) < 3:
            continue
        market_id, digits, name = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if "\\u" in name:
            try:
                name = name.encode("utf-8").decode("unicode_escape")
            except Exception:
                pass
        kind = parts[4].strip() if len(parts) > 4 else ""
        if market_id not in {"sh", "sz"}:
            continue
        if kind and kind not in {"GP-A", "JJ", "ETF", "LOF"} and not digits.startswith(("5", "1", "6", "0", "3")):
            continue
        code = f"{market_id}{digits}"
        rows.append({
            "code": code,
            "name": name or code,
            "type": "etf" if kind in {"JJ", "ETF", "LOF"} or _infer_type(code, name) == "etf" else "stock",
            "source": "tencent",
        })
    return rows


async def search_codes(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = (query or "").strip()
    n = max(1, min(int(limit or 8), 12))
    if not q:
        return []
    hits = _local_code_hits(q, limit=n)
    by_code = {h["code"]: h for h in hits}

    url = "https://smartbox.gtimg.cn/s3/"
    params = {"v": "2", "q": q, "t": "all"}
    text = ""
    for trust_env in (True, False):
        try:
            async with httpx.AsyncClient(trust_env=trust_env, timeout=6.0) as client:
                r = await client.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
                text = r.content.decode("utf-8", errors="ignore") or r.text
                if "v_hint=" in text:
                    break
        except Exception:
            continue
    for row in _parse_tencent_hint(text):
        prev = by_code.get(row["code"])
        if not prev:
            by_code[row["code"]] = row
            continue
        if not prev.get("name") or prev["name"] == prev["code"]:
            prev["name"] = row["name"]
            prev["type"] = row.get("type") or prev.get("type")
    return list(by_code.values())[:n]


def get_journal(limit: int = 5) -> list[dict[str, Any]]:
    journal = read_json("journal.json", []) or []
    n = max(1, min(int(limit or 5), 20))
    return list(journal[:n]) if isinstance(journal, list) else []
