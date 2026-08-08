"""盘面简报：拼快照 + 按知识库五段框架生成版本报告（同日可多版追加）。"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from app.core.config import settings
from app.infrastructure.llm import get_llm_client
from app.infrastructure.market.service import market
from app.infrastructure.persistence import analyses_store, positions_store, review_store, watch_store
from app.services.journal import list_journal
from app.services.lamps import compute_lamps, lamp_cap_from_lamps
from app.services.rag import retrieve_knowledge

_SENTIMENT_UP_PCT = 0.4
_SENTIMENT_UP_COUNT = 1500
_SENTIMENT_CAP = 0.3


def build_daily_review_snapshot() -> dict[str, Any]:
    """采集当日可核对硬数据（缺什么就标 gaps，禁止事后编造）。"""
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

    lamps = _compute_lamps_lite()
    lamp_info = lamp_cap_from_lamps(lamps)
    red = int(lamp_info["redCount"])
    lamp_cap = float(lamp_info["lampCap"])
    sentiment_cap = _SENTIMENT_CAP if retreat else None
    effective_cap = min(lamp_cap, sentiment_cap) if sentiment_cap is not None else lamp_cap

    sf = market.sector_flow_cache or {}
    sectors = list(sf.get("list") or [])
    by_inflow = sorted(sectors, key=lambda r: float(r.get("netInflow") or 0), reverse=True)
    by_strength = sorted(sectors, key=lambda r: float(r.get("strength") or 0), reverse=True)
    by_outflow = sorted(sectors, key=lambda r: float(r.get("netInflow") or 0))

    positions = positions_store.load_positions() or {}
    pos_rows: list[dict[str, Any]] = []
    for code, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        q = market.quote_cache.get(code) or {}
        k = market.kline_cache.get(code) or {}
        price = float(q.get("price") or 0)
        buy = float(pos.get("buyPrice") or 0)
        shares = float(pos.get("shares") or 0)
        pnl_pct = ((price - buy) / buy * 100) if buy > 0 and price > 0 else None
        ma20 = float(k.get("ma20") or 0)
        pos_rows.append(
            {
                "code": code,
                "name": q.get("name") or pos.get("name") or code,
                "price": price or None,
                "changePct": q.get("changePct"),
                "buyPrice": buy or None,
                "shares": shares or None,
                "pnlPct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "belowMA20": bool(ma20 > 0 and price > 0 and price < ma20),
                "liangbi": q.get("liangbi"),
            }
        )
    pos_rows.sort(key=lambda r: (r.get("pnlPct") is not None, r.get("pnlPct") or -999), reverse=True)

    analyses = analyses_store.load_analyses() or {}
    watch_codes = set(watch_store.load_watch_codes() or [])
    codes = set(positions.keys()) | set(analyses.keys()) | watch_codes
    weak_watch: list[dict[str, Any]] = []
    for code in list(codes)[:100]:
        q = market.quote_cache.get(code) or {}
        k = market.kline_cache.get(code) or {}
        price = float(q.get("price") or 0)
        ma20 = float(k.get("ma20") or 0)
        if ma20 > 0 and price > 0 and price < ma20:
            weak_watch.append(
                {
                    "code": code,
                    "name": q.get("name") or code,
                    "changePct": q.get("changePct"),
                    "belowMA20": True,
                }
            )
    weak_watch = weak_watch[:12]

    indices: dict[str, Any] = {}
    for code, name in (
        ("sh000001", "上证"),
        ("sz399001", "深成"),
        ("sz399006", "创业板"),
        ("sh000300", "沪深300"),
    ):
        q = market.index_cache.get(code) or {}
        if q:
            indices[code] = {
                "name": name,
                "price": q.get("price"),
                "changePct": q.get("changePct"),
            }

    journal = list_journal(limit=15)
    today = date.today().isoformat()

    missing: list[str] = []
    if not total:
        missing.append("全市场涨跌家数")
    if not sectors:
        missing.append("板块资金流向")
    if not indices:
        missing.append("主要指数")
    missing.extend(["股指期货加减仓", "个股主力净流入明细", "炸板率"])

    return {
        "date": today,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "market": {
            "indices": indices,
            "breadth": {
                "up": up,
                "down": down,
                "total": total,
                "upPct": round(up_pct * 100, 1) if up_pct is not None else None,
            },
            "overseas": market.overseas,
            "limitUpSummary": _limit_up_summary(),
            "sentimentRetreat": retreat,
            "lastUpdate": market.last_update,
        },
        "positionCap": {
            "lampRed": red,
            "riskScore": lamp_info["riskScore"],
            "hardScore": lamp_info["hardScore"],
            "softScore": lamp_info["softScore"],
            "lamps": lamps,
            "lampCap": lamp_cap,
            "sentimentCap": sentiment_cap,
            "effectiveCap": effective_cap,
            "buyAllowed": effective_cap > 0 and not retreat,
            "text": _cap_text(red, lamp_cap, sentiment_cap, effective_cap, retreat, lamp_info["riskScore"]),
        },
        "sectors": {
            "summary": sf.get("summary") or {},
            "topByInflow": [
                _sector_brief(r) for r in by_inflow[:8] if float(r.get("netInflow") or 0) > 0
            ],
            "topByStrength": [_sector_brief(r) for r in by_strength[:8]],
            "topOutflow": [
                _sector_brief(r) for r in by_outflow[:8] if float(r.get("netInflow") or 0) < 0
            ],
        },
        "positions": pos_rows,
        "weakWatch": weak_watch,
        "journalToday": [j for j in journal if str(j.get("ts") or "").startswith(today)][:20],
        "journalRecent": journal[:8],
        "dataGaps": missing,
        "note": "净流入额看体量；strength 为资金强度代理，不等于官方净流入率。",
    }


async def generate_brief(
    *,
    refresh_snapshot: bool = True,
    brief_date: str | None = None,
    base_version_id: int | None = None,
    mark_final: bool = False,
) -> dict[str, Any]:
    """追加一版盘面简报（永不覆盖旧版）。

    refresh_snapshot=True：重采当前盘面（默认今日）。
    base_version_id：用该版冻结快照 + 批注再生成**新**版本。
    """
    base = review_store.get_version(int(base_version_id)) if base_version_id else None
    if base_version_id and not base:
        raise ValueError("基准版本不存在")

    day = (brief_date or (base or {}).get("date") or date.today().isoformat())[:10]
    comments: list[dict[str, Any]] = []
    prior_report = ""

    if refresh_snapshot and not base_version_id:
        if not market.sector_flow_cache.get("list"):
            try:
                await market.fetch_all_quotes()
            except Exception:
                pass
        snapshot = build_daily_review_snapshot()
        snapshot["date"] = day
    else:
        if not base or not base.get("snapshot"):
            raise ValueError("没有基准快照，请先「采集盘面生成新版」或指定 baseVersionId")
        snapshot = base["snapshot"]
        day = str(base.get("date") or day)[:10]
        comments = list(base.get("comments") or [])
        prior_report = str(base.get("reportMd") or "")

    framework_hits = retrieve_knowledge(
        "日终复盘 盘面简报 资金叙事 验证窗口",
        top_k=4,
        extra_queries=["日终复盘五段框架", "情绪退潮 有效仓位"],
    )
    framework_text = "\n\n".join(
        f"[{h.get('path') or h.get('id')}]\n{(h.get('text') or '')[:1200]}" for h in framework_hits
    )
    history = review_store.recent_for_context(
        limit=5,
        exclude_id=int(base_version_id) if base_version_id else None,
    )
    report = await _llm_report(
        snapshot,
        framework_text,
        comments=comments,
        prior_report=prior_report,
        history_reviews=history,
    )
    saved = review_store.create_version(
        brief_date=day,
        snapshot=snapshot,
        report_md=report.get("markdown") or "",
        model=report.get("model") or "",
        comments=[],
        is_final=bool(mark_final),
    )
    return {
        "success": True,
        "version": saved,
        "day": review_store.get_day_bundle(day),
        "snapshot": snapshot,
        "report": report,
        "sources": [{"path": h.get("path"), "score": h.get("score")} for h in framework_hits],
    }


def list_brief_days(limit: int = 60) -> list[dict[str, Any]]:
    return review_store.list_days(limit=limit)


def get_brief_day(brief_date: str) -> dict[str, Any] | None:
    return review_store.get_day_bundle(brief_date)


def get_brief_version(version_id: int) -> dict[str, Any] | None:
    return review_store.get_version(version_id)


def add_brief_comment(version_id: int, text: str) -> dict[str, Any] | None:
    return review_store.add_comment(version_id, text)


def mark_brief_final(version_id: int) -> dict[str, Any] | None:
    return review_store.mark_final(version_id)


def _limit_up_summary() -> dict[str, Any] | None:
    lu = getattr(market, "limit_up_stats", None)
    if not isinstance(lu, dict) or not lu:
        return None
    keys = (
        "zt", "zb", "dt", "maxDays", "topSector", "ladder",
        "breakRate", "yestPremium", "yestPremiumSample",
        "promoteRate", "promoteEligible", "promoteSuccess",
        "bigDrawdown", "bigDrawdownThr", "yestDate",
        "upCount", "downCount", "limitUpCount",
    )
    return {k: lu.get(k) for k in keys if k in lu}


def _sector_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sectorName": row.get("sectorName"),
        "netInflow": row.get("netInflow"),
        "strength": row.get("strength"),
        "changePct": row.get("changePct"),
        "trend": row.get("trend"),
    }


def _cap_text(
    red: int,
    lamp_cap: float,
    sentiment_cap: float | None,
    effective: float,
    retreat: bool,
    risk_score: float = 0.0,
) -> str:
    if effective <= 0:
        return f"风险{risk_score:g} | 仓位归零"
    if retreat and sentiment_cap is not None and sentiment_cap < lamp_cap:
        return f"风险{risk_score:g} | 有效≤{int(round(effective * 10))}成（情绪退潮）"
    return f"{red}盏亮(风险{risk_score:g}) | 仓位上限{int(round(lamp_cap * 10))}成"


def _compute_lamps_lite() -> list[dict[str, Any]]:
    return compute_lamps(lever_red=False)


async def _llm_report(
    snapshot: dict[str, Any],
    framework_text: str,
    *,
    comments: list[dict[str, Any]] | None = None,
    prior_report: str = "",
    history_reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    key = (settings.llm_api_key or "").strip()
    if not key or "your-deepseek-key" in key or key == "missing":
        return {
            "markdown": _fallback_markdown(snapshot),
            "model": None,
            "mode": "template",
            "warning": "未配置 LLM，已输出结构化模板。",
        }

    system = """你是 Jarvis 盘面简报执笔（盘中/盘后均可）。只根据用户提供的材料写报告。
硬性要求：
1. 严格按五段：一句话定性 / 核心信号 / 博弈判断 / 定行动 / 验证窗口。
2. 只用快照里出现的数字与板块名；dataGaps 中的项必须写「数据不足」，禁止编造。
3. 若有【基准版批注】，必须吸收纠偏（例如验证失败、叙事降级），不要无视。
4. 若有【近期简报摘要】，可对照验证窗口是否兑现，但不要把过期行情写成「此刻」。
5. 区分净流入额与 strength；放量不涨价提示分歧量。
6. 行动不得突破 positionCap.effectiveCap；情绪退潮则只卖不买。
7. 验证窗口 2～3 条可证伪信号；结尾加：信息不构成投资建议。
8. 简体中文 Markdown，标题用 ##；可注明盘中或偏日终视角，但勿编造时间戳。"""

    parts = [
        f"【五段框架摘录（日终复盘.md）】\n{framework_text or '（检索为空，仍按五段写）'}",
        f"【本版冻结快照 JSON】\n{json.dumps(snapshot, ensure_ascii=False, default=str)[:12000]}",
    ]
    if comments:
        parts.append(
            "【基准版批注（新版必须参考）】\n"
            + "\n".join(f"- {c.get('ts')}: {c.get('text')}" for c in comments[-12:])
        )
    if prior_report.strip():
        parts.append(f"【基准版正文（可改写为新版，勿原样照抄）】\n{prior_report[:3500]}")
    if history_reviews:
        parts.append(
            "【近期简报摘要】\n"
            + json.dumps(history_reviews, ensure_ascii=False, default=str)[:2500]
        )
    user = "\n\n".join(parts)
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
        "markdown": text,
        "model": settings.llm_model,
        "mode": "llm",
        "warning": None,
    }


def _fallback_markdown(snapshot: dict[str, Any]) -> str:
    m = snapshot.get("market") or {}
    b = m.get("breadth") or {}
    cap = snapshot.get("positionCap") or {}
    sec = snapshot.get("sectors") or {}
    top = (sec.get("topByInflow") or [{}])[:1]
    top = top[0] if top else {}
    strong = (sec.get("topByStrength") or [{}])[:1]
    strong = strong[0] if strong else {}
    out = (sec.get("topOutflow") or [{}])[:1]
    out = out[0] if out else {}
    return "\n".join(
        [
            f"## {snapshot.get('date')} 盘面简报（模板）",
            "",
            f"**一句话定性：** 快照已就绪；{cap.get('text') or '仓位未知'}。配置 LLM 后可生成完整叙事。",
            "",
            "## 核心信号",
            f"- 涨跌家数：↑{b.get('up')} ↓{b.get('down')}（上涨占比 {b.get('upPct')}%）"
            f"{'；情绪退潮中' if m.get('sentimentRetreat') else ''}",
            f"- 流入额靠前：{top.get('sectorName')} {top.get('netInflow')} 亿",
            f"- 强度靠前：{strong.get('sectorName')} strength={strong.get('strength')}",
            f"- 流出靠前：{out.get('sectorName')} {out.get('netInflow')} 亿",
            "",
            "## 博弈判断",
            "- （待 LLM）结合板块切换与持仓强弱。",
            "",
            "## 定行动",
            f"- 有效仓位上限：{cap.get('effectiveCap')}",
            "- 遵守铁律与利空门禁；不追连板。",
            "",
            "## 验证窗口",
            "- 情绪退潮是否缓解",
            "- 今日强度最高板块次日是否仍强",
            "- 持仓破 20 日线只数是否扩大",
            "",
            f"数据缺口：{', '.join(snapshot.get('dataGaps') or [])}",
            "",
            "信息不构成投资建议。",
        ]
    )
