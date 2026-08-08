"""策略选股 / 竞价 / 板块资金。

打分仍在 market 层；本层叠加纪律滤镜、策略元数据与可选 LLM 深析。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.infrastructure.llm import get_llm_client
from app.infrastructure.market.service import market
from app.infrastructure.persistence import positions_store, watch_store

from app.services.lamps import compute_lamps, lamp_cap_from_lamps
from app.services.rag import retrieve_knowledge

_SENTIMENT_UP_PCT = 0.4
_SENTIMENT_UP_COUNT = 1500
_SENTIMENT_CAP = 0.3

STRATEGIES = [
    {
        "id": "trend",
        "name": "趋势波段",
        "badge": "L1 观察",
        "doc": "趋势波段策略.md",
        "topN": 5,
        "scoreKey": "trendScore",
        "resultsKey": "trendResults",
        "candidatesKey": "trendCandidates",
        "blurb": "站上 MA20 + 趋势结构排序；忌末端追高",
    },
    {
        "id": "pullback",
        "name": "趋势回踩",
        "badge": "L1 观察",
        "doc": "趋势回踩策略.md",
        "topN": 5,
        "scoreKey": "pullbackScore",
        "resultsKey": "pullbackResults",
        "candidatesKey": "pullbackCandidates",
        "blurb": "上升趋势中缩量回踩 MA20 观察带",
    },
    {
        "id": "flow",
        "name": "资金共振",
        "badge": "L1 观察",
        "doc": "资金共振策略.md",
        "topN": 5,
        "scoreKey": "flowScore",
        "resultsKey": "flowResults",
        "candidatesKey": "flowCandidates",
        "blurb": "板块资金强度 Top8 ∩ 个股趋势未坏",
    },
    {
        "id": "quality",
        "name": "综合质量",
        "badge": "多因子",
        "doc": "盘后选股与竞价异动.md",
        "topN": 10,
        "scoreKey": "score",
        "resultsKey": "results",
        "candidatesKey": None,
        "blurb": "估值 + 趋势 + 量能，与自选综合分同口径",
    },
]


async def screen_top() -> dict[str, Any]:
    raw = await market.screen_top()
    return _enrich_payload(raw, kind="screen")


async def auction_top() -> dict[str, Any]:
    raw = await market.auction_top()
    return _enrich_payload(raw, kind="auction")


async def sector_flow() -> dict[str, Any]:
    if not market.sector_flow_cache.get("list"):
        await market.fetch_all_quotes()
    return market.sector_flow_cache


def build_discipline_context() -> dict[str, Any]:
    """与盘面简报 / 前端有效仓位同口径的软门禁（用于榜单提示，不改打分）。"""
    mb = market.market_breadth or {}
    breadth = market.breadth or {}
    use_mb = mb if (mb.get("total") or 0) > 0 else breadth
    up = int(use_mb.get("up") or 0)
    down = int(use_mb.get("down") or 0)
    total = int(use_mb.get("total") or 0) or (up + down)
    up_pct = (up / total) if total else None

    retreat = False
    if total > 0 and up_pct is not None:
        retreat = up_pct < _SENTIMENT_UP_PCT or (
            (mb.get("total") or 0) > 0 and up < _SENTIMENT_UP_COUNT
        )

    lamps = compute_lamps(lever_red=False)
    lamp_info = lamp_cap_from_lamps(lamps)
    red = int(lamp_info["redCount"])
    lamp_cap = float(lamp_info["lampCap"])
    sentiment_cap = _SENTIMENT_CAP if retreat else None
    effective = min(lamp_cap, sentiment_cap) if sentiment_cap is not None else lamp_cap
    buy_allowed = effective > 0 and not retreat

    if effective <= 0:
        text = f"风险{lamp_info['riskScore']:g} | 仓位归零"
        hint = "今日不宜新开（仓位归零）"
    elif retreat:
        text = f"风险{lamp_info['riskScore']:g} | 有效≤{int(round(effective * 10))}成（情绪退潮）"
        hint = "情绪退潮：只卖不买，榜单仅作观察"
    else:
        text = lamp_info["text"]
        hint = ""

    return {
        "sentimentRetreat": retreat,
        "lampRed": red,
        "riskScore": lamp_info["riskScore"],
        "hardScore": lamp_info["hardScore"],
        "softScore": lamp_info["softScore"],
        "lampCap": lamp_cap,
        "sentimentCap": sentiment_cap,
        "effectiveCap": effective,
        "buyAllowed": buy_allowed,
        "text": text,
        "hint": hint,
        "breadth": {
            "up": up,
            "down": down,
            "total": total,
            "upPct": round(up_pct * 100, 1) if up_pct is not None else None,
        },
    }


def enrich_screen_row(
    row: dict[str, Any],
    *,
    discipline: dict[str, Any],
    positions: set[str],
    watch: set[str],
    kind: str,
) -> dict[str, Any]:
    """给单行挂 flags + 对齐知识库的信号（不改 score）。"""
    out = dict(row)
    code = str(out.get("code") or "")
    signals = list(out.get("signals") or [])
    lb = float(out.get("liangbi") or 0)
    chg = float(out.get("changePct") or 0)

    in_pos = code in positions
    in_watch = code in watch
    below_ma20 = None
    if "aboveMA20" in out and out.get("ma20"):
        below_ma20 = not bool(out.get("aboveMA20"))
    else:
        k = market.kline_cache.get(code) or {}
        q_price = float(out.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if ma20 > 0 and q_price > 0:
            below_ma20 = q_price < ma20

    if lb >= 2.5 and chg <= -3:
        _add_signal(signals, "放量下跌警惕")
    elif lb >= 2 and chg < 1:
        _add_signal(signals, "放量滞涨")

    broke_open = None
    if kind == "auction":
        open_p = float(out.get("open") or 0)
        price = float(out.get("price") or 0)
        if open_p > 0 and price > 0:
            vs = (price - open_p) / open_p * 100
            out["vsOpenPct"] = round(vs, 2)
            if vs < -0.3:
                broke_open = True
                _add_signal(signals, f"现价破开盘{vs:.1f}%")
            elif vs > 0.3:
                broke_open = False
                _add_signal(signals, f"站上开盘+{vs:.1f}%")
            else:
                broke_open = False
                _add_signal(signals, "贴着开盘价")

    if in_pos:
        _add_signal(signals, "已持仓", front=True)
    if in_pos and below_ma20:
        _add_signal(signals, "持仓破20日线", front=True)
    elif below_ma20 and kind in ("screen", "quality", "trend", "pullback", "flow"):
        _add_signal(signals, "破20日线")

    buy_discouraged = not bool(discipline.get("buyAllowed"))
    if buy_discouraged:
        _add_signal(signals, "纪律:不宜新开")

    why = list(out.get("why") or [])
    if buy_discouraged and "纪律：不宜新开仓" not in why:
        why.append("纪律：不宜新开仓")
    out["why"] = why[:8]

    out["flags"] = {
        "inPosition": in_pos,
        "inWatch": in_watch,
        "belowMA20": below_ma20,
        "brokeOpen": broke_open,
        "buyDiscouraged": buy_discouraged,
    }
    out["signals"] = signals[:10]
    return out


def _trend_stage(discipline: dict[str, Any]) -> dict[str, Any]:
    if not discipline.get("buyAllowed"):
        if discipline.get("sentimentRetreat"):
            return {
                "stage": "退潮",
                "eligible": False,
                "note": "情绪退潮或仓位受限：榜单仅供观察，不宜新开",
            }
        return {
            "stage": "谨慎",
            "eligible": False,
            "note": "有效仓位过严：榜单仅供观察",
        }
    red = int(discipline.get("lampRed") or discipline.get("riskScore") or 0)
    if red >= 2:
        return {
            "stage": "谨慎",
            "eligible": True,
            "note": "五灯偏高，短名单可看、开仓宜更严",
        }
    return {
        "stage": "可做趋势",
        "eligible": True,
        "note": "未退潮：L1 短名单≠可买入",
    }


def _enrich_payload(raw: dict[str, Any], *, kind: str) -> dict[str, Any]:
    discipline = build_discipline_context()
    positions = set((positions_store.load_positions() or {}).keys())
    watch = set(watch_store.load_watch_codes() or [])
    results = [
        enrich_screen_row(r, discipline=discipline, positions=positions, watch=watch, kind=kind)
        for r in (raw.get("results") or [])
        if isinstance(r, dict)
    ]
    out = dict(raw)
    out["results"] = results
    out["discipline"] = discipline
    out["kind"] = kind
    if kind == "screen":
        stage = _trend_stage(discipline)
        strategies = []
        for meta in STRATEGIES:
            key = meta["resultsKey"]
            rows_raw = raw.get(key) if key != "results" else results
            if key == "results":
                rows = results
            else:
                rows = [
                    enrich_screen_row(
                        r,
                        discipline=discipline,
                        positions=positions,
                        watch=watch,
                        kind=meta["id"],
                    )
                    for r in (rows_raw or [])
                    if isinstance(r, dict)
                ]
                out[key] = rows
            cand_key = meta.get("candidatesKey")
            candidates = int(raw.get(cand_key) or len(rows)) if cand_key else len(rows)
            strategies.append({
                **meta,
                **stage,
                "candidates": candidates,
                "shown": len(rows),
                "rows": rows,
            })
        out["strategies"] = strategies
        out["trendMeta"] = {
            **stage,
            "candidates": int(raw.get("trendCandidates") or 0),
            "shown": len(out.get("trendResults") or []),
            "doc": "趋势波段策略.md",
        }
        out["title"] = "策略选股"
    return out


def get_strategy_doc(strategy_id: str) -> dict[str, Any]:
    """策略选股页可读的策略原文（仅允许 STRATEGIES 白名单，无需 kb.manage）。"""
    meta = next((s for s in STRATEGIES if s["id"] == strategy_id), None)
    if not meta:
        return {"ok": False, "error": "unknown_strategy"}
    rel = str(meta["doc"])
    root = settings.knowledge_dir.resolve()
    full = (root / rel).resolve()
    if root not in full.parents and full != root:
        return {"ok": False, "error": "bad_path"}
    if not full.is_file():
        return {"ok": False, "error": "not_found", "path": rel}
    return {
        "ok": True,
        "strategyId": strategy_id,
        "path": rel,
        "name": meta["name"],
        "content": full.read_text(encoding="utf-8"),
    }


async def analyze_screen_pick(
    *,
    strategy_id: str,
    code: str,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """按需深析：策略条文 + 入选理由 + 行情摘要 → 短评（非买卖指令）。"""
    meta = next((s for s in STRATEGIES if s["id"] == strategy_id), None)
    if not meta:
        return {"ok": False, "error": "unknown_strategy"}

    snap = dict(row or {})
    if not snap.get("code"):
        snap["code"] = code
    if not snap.get("name"):
        q = (market.quotes_cache or {}).get(code) or {}
        snap["name"] = q.get("name") or code

    doc = meta["doc"]
    chunks = retrieve_knowledge(
        f"{meta['name']} {doc} 入选 门禁",
        top_k=4,
        extra_queries=[doc.replace(".md", ""), meta["name"]],
    ) or []
    framework = "\n\n".join(
        f"[{c.get('source') or doc}]\n{c.get('text') or ''}" for c in chunks
    )[:4500]
    # Milvus 空/未 reindex 时回退读策略原文，避免「按常识编造」
    if not framework.strip():
        file_doc = get_strategy_doc(strategy_id)
        if file_doc.get("ok") and file_doc.get("content"):
            framework = f"[{doc}]\n{str(file_doc['content'])[:4500]}"

    why = snap.get("why") or snap.get("signals") or []
    discipline = build_discipline_context()

    key = (settings.llm_api_key or "").strip()
    if not key or "your-deepseek-key" in key or key == "missing":
        bullets = "\n".join(f"- {w}" for w in why[:6]) or "- （无规则理由）"
        md = (
            f"### {snap.get('name')} · {meta['name']}\n\n"
            f"**规则匹配**\n{bullets}\n\n"
            f"**纪律**：{discipline.get('text') or '--'}\n\n"
            "未配置 LLM，以上为规则摘要。信息不构成投资建议；加入自选后仍须利空复核。"
        )
        return {"ok": True, "markdown": md, "mode": "rules", "model": None, "strategy": meta}

    system = """你是 Jarvis 策略选股/自选深析助手。只根据用户材料写简短分析。
硬性要求：
1. 用简体中文 Markdown，三段：匹配点 / 风险点 / 行动边界。
2. 匹配点必须复述或改写「规则入选理由」，禁止编造未给出的题材/业绩/主力故事。
3. 若材料含持仓/自选：重点写「对照门禁与铁律，现在该观察、减仓还是继续」；不宜新开则明确只观察。
4. 行动不得突破纪律；强调评分达标≠可买入，须利空门禁。
5. 全文不超过 280 字；结尾加：信息不构成投资建议。"""

    user = (
        f"【策略】{meta['name']}（{doc}）\n"
        f"【策略摘录】\n{framework or '（检索为空，按策略常识与理由写）'}\n\n"
        f"【候选 JSON】\n{json.dumps(snap, ensure_ascii=False, default=str)[:2500]}\n\n"
        f"【规则入选理由】\n" + "\n".join(f"- {w}" for w in why[:8]) + "\n\n"
        f"【当日纪律】{discipline.get('text')}；buyAllowed={discipline.get('buyAllowed')}"
    )
    client = get_llm_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return {
        "ok": True,
        "markdown": text,
        "mode": "llm",
        "model": settings.llm_model,
        "strategy": meta,
    }


def _add_signal(signals: list[str], text: str, *, front: bool = False) -> None:
    if text in signals:
        return
    if front:
        signals.insert(0, text)
    else:
        signals.append(text)
