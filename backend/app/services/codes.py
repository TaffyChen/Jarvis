"""观察池：搜索 / 添加 / 移除。"""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.domain.codes import normalize_code
from app.infrastructure.market.service import market
from app.infrastructure.persistence.analyses_store import load_analyses, save_analyses


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
    analyses = load_analyses() or {}
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


def add_code(
    code: str,
    *,
    name: str | None = None,
    type: str | None = None,
    notes: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    c = normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code", "code": code}

    added = False
    if c not in market.stock_codes:
        market.stock_codes.append(c)
        added = True
        if save:
            market.save_codes()

    analyses = load_analyses() or {}
    row = analyses.get(c) or {"code": c}
    row["code"] = c
    if name:
        row["name"] = name
    else:
        row.setdefault("name", c)
    if type:
        row["type"] = type
    elif c.startswith(("sh5", "sz1")):
        row["type"] = "etf"
    else:
        row.setdefault("type", "stock")
    if notes:
        row["notes"] = notes
    analyses[c] = row
    save_analyses(analyses)

    return {
        "ok": True,
        "code": c,
        "added_to_universe": added,
        "name": row.get("name"),
        "type": row.get("type"),
        "need_quotes": added,
    }


def add_codes(codes: list[Any]) -> dict[str, Any]:
    added = 0
    need_quotes = False
    for raw in codes or []:
        c = normalize_code(raw) if raw else ""
        if not c:
            c = str(raw or "").strip().lower()
        if not c:
            continue
        r = add_code(c, save=True)
        if r.get("added_to_universe"):
            added += 1
        if r.get("need_quotes"):
            need_quotes = True
    return {
        "success": True,
        "added": added,
        "total": len(market.stock_codes),
        "need_quotes": need_quotes,
    }


def remove_codes(codes: list[Any]) -> dict[str, Any]:
    removed = 0
    for c in codes or []:
        if c in market.stock_codes:
            market.stock_codes.remove(c)
            market.quote_cache.pop(c, None)
            market.kline_cache.pop(c, None)
            removed += 1
    if removed:
        market.save_codes()
    return {"success": True, "removed": removed, "total": len(market.stock_codes)}
