"""HITL 确认后的 strategy_patch 执行。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.codes import normalize_code
from app.infrastructure.market.service import market
from app.infrastructure.persistence.analyses_store import load_analyses, save_analyses
from app.infrastructure.persistence.journal_store import add_journal_entry
from app.infrastructure.persistence.positions_store import load_positions, save_positions
from app.infrastructure.persistence.proposals_store import load_proposals, save_proposals
from app.services.positions import remove_position, resolve_position_code


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def apply_strategy_patch(patch: dict | None) -> dict[str, Any]:
    patch = patch or {}
    applied: list[dict] = []
    analyses = load_analyses() or {}
    proposals = load_proposals() or []
    positions = load_positions() or {}
    if not isinstance(positions, dict):
        positions = {}
    need_quotes = False
    codes_dirty = False

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
            if action in ("remove", "delete", "clear"):
                key = (
                    code
                    or payload.get("name")
                    or p.get("name")
                    or p.get("code")
                    or payload.get("code")
                )
                r = remove_position(str(key or ""))
                if r.get("ok"):
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
            for key_src, key_dst in (
                ("stopLossPrice", "stopLossPrice"),
                ("stop_loss_price", "stopLossPrice"),
                ("takeProfitPrice", "takeProfitPrice"),
                ("take_profit_price", "takeProfitPrice"),
            ):
                if key_src not in payload:
                    continue
                raw_lv = payload.get(key_src)
                if raw_lv in (None, "", 0, "0"):
                    pos.pop(key_dst, None)
                    continue
                try:
                    lv = float(raw_lv)
                except (TypeError, ValueError):
                    continue
                if lv > 0:
                    pos[key_dst] = lv
                else:
                    pos.pop(key_dst, None)
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
            add_journal_entry(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "info",
                    "msg": payload.get("msg") or patch.get("summary") or "Jarvis 提案",
                    "action": payload.get("action") or "策略更新",
                    "note": payload.get("note") or "",
                    "name": "Jarvis",
                    "code": code or "",
                }
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

    save_analyses(analyses)
    save_proposals((proposals or [])[:200])
    save_positions(positions)

    return {
        "success": True,
        "applied": True,
        "items": applied,
        "need_quotes": need_quotes,
        "summary": patch.get("summary"),
    }
