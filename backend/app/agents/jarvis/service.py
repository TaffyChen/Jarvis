from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from app.core.llm import SYSTEM_PROMPT, get_llm_client
from app.core.local_kb import get_store
from app.core.storage import read_json, write_json
from app.config import settings
from app.services.market.service import market


def _context_snapshot() -> str:
    positions = read_json("positions.json", {})
    analyses = read_json("analyses.json", {})
    journal = read_json("journal.json", [])
    lines = ["## 当前持仓"]
    if not positions:
        lines.append("（空仓）")
    else:
        for code, p in positions.items():
            q = market.quote_cache.get(code) or {}
            lines.append(
                f"- {code} 成本{p.get('buyPrice')} 股数{p.get('shares')} "
                f"现价{q.get('price','?')} 涨跌{q.get('changePct','?')}%"
            )
    lines.append("\n## 近期日记")
    for j in (journal or [])[:5]:
        lines.append(f"- {j.get('ts','')[:16]} {j.get('name','')}: {j.get('msg','')} → {j.get('action','')}")
    lines.append("\n## 分析摘要（部分）")
    n = 0
    for code, a in (analyses or {}).items():
        if n >= 8:
            break
        lines.append(
            f"- {a.get('name', code)} riskOk={a.get('riskOk')} reviewedAt={a.get('reviewedAt')} "
            f"reason={a.get('reason','')[:60]}"
        )
        n += 1
    ov = market.overseas
    if ov:
        lines.append(f"\n## 海外 标普 {ov.get('changePct')}%")
    mb = market.market_breadth
    lines.append(f"全市场涨跌 {mb.get('up')}/{mb.get('down')}")
    return "\n".join(lines)


def _extract_patch(text: str) -> dict | None:
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
        if obj.get("type") == "strategy_patch":
            return obj
    except Exception:
        return None
    return None


async def ask_jarvis(question: str, history: list[dict] | None = None) -> dict[str, Any]:
    hits = get_store().search(question, top_k=5)
    kb_text = "\n\n".join(
        f"[{h['source']} | score={h['score']}]\n{h['text']}" for h in hits
    ) or "（知识库暂无命中，请先运行 reindex）"
    snap = _context_snapshot()
    user_block = (
        f"用户问题：{question}\n\n"
        f"### 检索片段\n{kb_text}\n\n"
        f"### 实时上下文\n{snap}"
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_block})

    if not settings.llm_api_key or "your-deepseek-key" in settings.llm_api_key:
        answer = (
            "尚未配置有效的 LLM_API_KEY。请在 Jarvis/.env 中设置 DeepSeek Key 后重试。\n\n"
            f"我已检索到 {len(hits)} 条本地知识，可先阅读：\n"
            + "\n".join(f"- {h['source']}: {h['text'][:80]}..." for h in hits)
        )
        return {"answer": answer, "sources": hits, "patch": None, "model": None}

    client = get_llm_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.3,
    )
    answer = resp.choices[0].message.content or ""
    patch = _extract_patch(answer)
    # persist conversation snippet lightly
    conv = read_json("conversations.json", [])
    conv.insert(
        0,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "answer": answer[:4000],
            "sources": [{"source": h["source"], "score": h["score"]} for h in hits],
            "patch": patch,
        },
    )
    write_json("conversations.json", conv[:100])
    return {
        "answer": answer,
        "sources": hits,
        "patch": patch,
        "model": settings.llm_model,
    }


async def ask_jarvis_stream(question: str, history: list[dict] | None = None) -> AsyncIterator[str]:
    """Yield SSE data lines."""
    result = await ask_jarvis(question, history)
    # For v1: non-token stream, chunk the answer for UX
    answer = result["answer"]
    step = 48
    for i in range(0, len(answer), step):
        yield json.dumps({"type": "delta", "text": answer[i : i + step]}, ensure_ascii=False)
    yield json.dumps(
        {
            "type": "done",
            "sources": result["sources"],
            "patch": result["patch"],
            "model": result["model"],
        },
        ensure_ascii=False,
    )
