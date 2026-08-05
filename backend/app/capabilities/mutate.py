"""写入能力：加标的 / 持仓 / 执行 strategy_patch / 沉淀。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.codes import normalize_code
from app.domain.memory import apply_memory_patch
from app.infra.market.service import market
from app.infra.storage import read_json, write_json


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def add_code(
    code: str,
    *,
    name: str | None = None,
    type: str | None = None,
    notes: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """加入观察池，并确保 analyses 有底稿。"""
    c = normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code", "code": code}

    added = False
    if c not in market.stock_codes:
        market.stock_codes.append(c)
        added = True
        if save:
            market.save_codes()

    analyses = read_json("analyses.json", {}) or {}
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
    write_json("analyses.json", analyses)

    return {
        "ok": True,
        "code": c,
        "added_to_universe": added,
        "name": row.get("name"),
        "type": row.get("type"),
        "need_quotes": added,
    }


def upsert_position(
    code: str,
    buy_price: float | int | str,
    shares: float | int | str,
    *,
    name: str | None = None,
    ensure_in_universe: bool = True,
) -> dict[str, Any]:
    """写入/更新持仓；默认同时确保进入观察池。"""
    c = normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code", "code": code}
    try:
        buy_f = float(buy_price)
        shares_f = float(shares)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_price_or_shares", "code": c}

    positions = read_json("positions.json", {}) or {}
    if not isinstance(positions, dict):
        positions = {}
    pos = positions.get(c) or {}
    pos["buyPrice"] = buy_f
    pos["shares"] = shares_f
    if name:
        pos["name"] = name
    positions[c] = pos
    write_json("positions.json", positions)

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


def resolve_position_code(raw: str | None) -> str:
    """代码或持仓名称 → 规范化 code。例：美的集团 / 000333 → sz000333。"""
    c = normalize_code(raw)
    if c:
        return c
    name = str(raw or "").strip()
    if not name:
        return ""
    positions = read_json("positions.json", {}) or {}
    if not isinstance(positions, dict):
        return ""
    # 精确匹配名称
    for code, p in positions.items():
        if (p.get("name") or "") == name:
            return code
    # 包含匹配（「删掉美的」）
    for code, p in positions.items():
        n = p.get("name") or ""
        if name in n or n in name:
            return code
    return ""


def remove_position(code: str) -> dict[str, Any]:
    """从持仓中删除（不自动移出观察池）。支持代码或名称。"""
    c = resolve_position_code(code) or normalize_code(code)
    if not c:
        return {"ok": False, "error": "bad_code_or_name", "input": code}

    positions = read_json("positions.json", {}) or {}
    if not isinstance(positions, dict):
        positions = {}
    if c not in positions:
        return {"ok": False, "error": "not_in_positions", "code": c}

    removed = positions.pop(c)
    write_json("positions.json", positions)
    return {
        "ok": True,
        "code": c,
        "name": removed.get("name"),
        "removed": True,
    }


def apply_strategy_patch(patch: dict | None) -> dict[str, Any]:
    """执行已确认的 strategy_patch（多 target）。"""
    patch = patch or {}
    applied: list[dict] = []
    analyses = read_json("analyses.json", {}) or {}
    journal = read_json("journal.json", []) or []
    proposals = read_json("strategy_proposals.json", []) or []
    positions = read_json("positions.json", {}) or {}
    if not isinstance(positions, dict):
        positions = {}
    need_quotes = False
    codes_dirty = False

    # patch 是“批量提案”：这里按顺序逐条应用，便于前端回显每条结果。
    for p in patch.get("patches") or []:
        target = p.get("target")
        action = p.get("action")
        payload = p.get("payload") or {}
        code = normalize_code(p.get("code") or payload.get("code"))

        if target == "codes" and action in ("add", "add_code", None, ""):
            if not code:
                continue
            if code not in market.stock_codes:
                market.stock_codes.append(code)
                codes_dirty = True
                need_quotes = True
            row = analyses.get(code) or {"code": code}
            row["code"] = code
            if payload.get("name"):
                row["name"] = payload["name"]
            else:
                row.setdefault("name", code)
            if payload.get("type"):
                row["type"] = payload["type"]
            elif code.startswith(("sh5", "sz1")):
                row["type"] = "etf"
            else:
                row.setdefault("type", "stock")
            if payload.get("notes"):
                row["notes"] = payload["notes"]
            analyses[code] = row
            applied.append({"target": "codes", "code": code, "action": "add"})

        elif target == "positions":
            # 删除持仓：action=remove|delete|clear；可用 code 或 payload.name
            if action in ("remove", "delete", "clear"):
                # 允许 code 字段直接写名称（如「美的集团」）
                key = (
                    code
                    or payload.get("name")
                    or p.get("name")
                    or p.get("code")
                    or payload.get("code")
                )
                r = remove_position(str(key or ""))
                if r.get("ok"):
                    # remove_position 已写盘；同步内存副本，末尾 write 不会把删掉的写回去
                    rc = r.get("code")
                    if rc and rc in positions:
                        del positions[rc]
                    applied.append(
                        {
                            "target": "positions",
                            "code": rc,
                            "name": r.get("name"),
                            "action": "remove",
                        }
                    )
                else:
                    applied.append(
                        {
                            "target": "positions",
                            "code": key,
                            "action": "remove_failed",
                            "error": r.get("error"),
                        }
                    )
                continue

            if not code:
                key = payload.get("name") or p.get("name")
                if key:
                    # 允许用户只给名称（如“美的集团”），这里做名称 -> code 解析。
                    code = resolve_position_code(str(key))
            if not code:
                applied.append({"target": "positions", "action": "skipped_no_code"})
                continue
            buy = payload.get("buyPrice", payload.get("buy_price"))
            shares = payload.get("shares")
            try:
                buy_f = float(buy) if buy is not None else None
                shares_f = float(shares) if shares is not None else None
            except (TypeError, ValueError):
                buy_f = shares_f = None
            if buy_f is None or shares_f is None:
                applied.append(
                    {"target": "positions", "code": code, "action": "skipped_missing_fields"}
                )
                continue
            pos = positions.get(code) or {}
            pos["buyPrice"] = buy_f
            pos["shares"] = shares_f
            if payload.get("name"):
                pos["name"] = payload["name"]
            positions[code] = pos
            if code not in market.stock_codes:
                market.stock_codes.append(code)
                codes_dirty = True
                need_quotes = True
            applied.append({"target": "positions", "code": code, "action": "upsert"})
        elif target == "analyses" and code:
            row = analyses.get(code) or {"code": code, "name": payload.get("name") or code}
            if action == "update_riskOk" and "riskOk" in payload:
                row["riskOk"] = payload["riskOk"]
                row["reviewedAt"] = _today()
            note = payload.get("notes") or payload.get("note")
            if action == "add_note" and note:
                row["notes"] = note
                row["reviewedAt"] = _today()
            analyses[code] = row
            applied.append({"code": code, "action": action, "target": "analyses"})

        elif target == "journal":
            journal.insert(
                0,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "info",
                    "msg": payload.get("msg") or patch.get("summary") or "Jarvis 提案",
                    "action": payload.get("action") or "策略更新",
                    "note": payload.get("note") or "",
                    "name": "Jarvis",
                    "code": code or "",
                },
            )
            applied.append({"target": "journal", "action": action})

        elif target == "rules":
            proposals.insert(
                0,
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "summary": patch.get("summary"),
                    "payload": payload,
                    "status": "accepted",
                },
            )
            applied.append({"target": "rules", "action": action})

    if codes_dirty:
        market.save_codes()

    write_json("analyses.json", analyses)
    write_json("journal.json", (journal or [])[:500])
    write_json("strategy_proposals.json", (proposals or [])[:200])
    write_json("positions.json", positions)

    return {
        "success": True,
        "applied": True,
        "items": applied,
        "need_quotes": need_quotes,
        "summary": patch.get("summary"),
    }


def apply_memory_notes(patch: dict | None, *, source_question: str = "") -> dict[str, Any]:
    return apply_memory_patch(patch or {}, source_question=source_question)
