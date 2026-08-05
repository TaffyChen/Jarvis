"""持仓读写。"""
from __future__ import annotations

from typing import Any

from app.domain.codes import normalize_code
from app.infrastructure.market.service import market
from app.infrastructure.persistence.positions_store import load_positions, save_positions
from app.services.codes import add_code


def list_positions_map() -> dict[str, Any]:
    data = load_positions() or {}
    return data if isinstance(data, dict) else {}


def save_positions_map(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    save_positions(payload)
    return {"success": True}


def get_positions() -> list[dict[str, Any]]:
    rows = []
    for code, p in list_positions_map().items():
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


def resolve_position_code(raw: str | None) -> str:
    c = normalize_code(raw)
    if c:
        return c
    name = str(raw or "").strip()
    if not name:
        return ""
    positions = list_positions_map()
    for code, p in positions.items():
        if (p.get("name") or "") == name:
            return code
    for code, p in positions.items():
        n = p.get("name") or ""
        if name in n or n in name:
            return code
    return ""


def upsert_position(
    code: str,
    buy_price: float | int | str,
    shares: float | int | str,
    *,
    name: str | None = None,
    ensure_in_universe: bool = True,
) -> dict[str, Any]:
    c = normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code", "code": code}
    try:
        buy_f = float(buy_price)
        shares_f = float(shares)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_price_or_shares", "code": c}

    positions = list_positions_map()
    pos = positions.get(c) or {}
    pos["buyPrice"] = buy_f
    pos["shares"] = shares_f
    if name:
        pos["name"] = name
    positions[c] = pos
    save_positions(positions)

    need_quotes = False
    if ensure_in_universe:
        r = add_code(c, name=name, save=True)
        need_quotes = bool(r.get("need_quotes"))

    return {
        "ok": True,
        "code": c,
        "buyPrice": buy_f,
        "shares": shares_f,
        "need_quotes": need_quotes,
    }


def remove_position(code: str) -> dict[str, Any]:
    c = resolve_position_code(code) or normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code_or_name", "input": code}

    positions = list_positions_map()
    if c not in positions:
        return {"ok": False, "error": "not_in_positions", "code": c}

    removed = positions.pop(c)
    save_positions(positions)
    return {
        "ok": True,
        "code": c,
        "name": removed.get("name"),
        "removed": True,
    }
