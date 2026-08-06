"""对话 RAG：查询改写 + 多路召回 + RRF + 可选 rerank。"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.domain.codes import normalize_code
from app.services.memory import search_memories
from app.infrastructure.kb.rerank import rerank_hits, rerank_info
from app.infrastructure.kb.search import rrf_fuse
from app.infrastructure.kb.index import get_store
from app.infrastructure.market.service import market

_CODE_RE = re.compile(r"(?:sh|sz)?\d{5,6}", re.I)
_HOLD_KEYS = ("持有", "减仓", "清仓", "仓位", "还能", "要不要", "卖", "买", "加仓")
_MAIN_KEYS = ("主升", "冰点", "第一天")
_MOOD_KEYS = ("情绪", "五灯", "市场", "灯")
_RISK_KEYS = ("利空", "门禁", "复核", "风险")
_REVIEW_KEYS = ("复盘", "日终", "资金故事", "验证窗口")


def expand_retrieval_queries(question: str, history: list[dict] | None = None) -> list[str]:
    """会话感知查询扩展（不额外打 LLM，延迟低）。"""
    q = (question or "").strip()
    if not q:
        return []
    queries = [q]
    codes: list[str] = []
    names: list[str] = []
    for text in _history_texts(history) + [q]:
        for raw in _CODE_RE.findall(text or ""):
            c = normalize_code(raw) or raw.lower()
            if c and c not in codes:
                codes.append(c)
        for name in _guess_names(text or ""):
            if name not in names:
                names.append(name)
    for c in codes:
        nm = ((market.quote_cache.get(c) or {}).get("name") or "").strip()
        if nm and nm not in names:
            names.append(nm)

    ctx = " ".join(names[:3] + codes[:3]).strip()
    if ctx and ctx not in q:
        queries.append(f"{q} {ctx}".strip())

    extra = ""
    if any(k in q for k in _HOLD_KEYS):
        extra = "持仓预警 五灯仓位 利空门禁"
    elif any(k in q for k in _MAIN_KEYS):
        extra = "主升第一天"
    elif any(k in q for k in _MOOD_KEYS):
        extra = "市场情绪四条件 五灯仓位"
    elif any(k in q for k in _RISK_KEYS):
        extra = "三原则两防线 评分与分类 利空"
    elif any(k in q for k in _REVIEW_KEYS):
        extra = "日终复盘 五灯仓位 情绪退潮"
    if extra:
        queries.append(f"{q} {extra}".strip())

    out: list[str] = []
    seen: set[str] = set()
    for item in queries:
        key = re.sub(r"\s+", " ", item).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out[:3]


def retrieve_knowledge(
    query: str,
    top_k: int = 5,
    extra_queries: list[str] | None = None,
    candidate_k: int | None = None,
) -> list[dict[str, Any]]:
    k = max(1, min(int(top_k or 5), 8))
    pool = max(k, int(candidate_k or settings.rag_candidate_k or 12))
    queries = [query] if (query or "").strip() else []
    for q in extra_queries or []:
        if (q or "").strip() and q.strip() not in queries:
            queries.append(q.strip())
    if not queries:
        return []

    store = get_store()
    rank_lists = []
    for q in queries[:3]:
        try:
            hits = store.search(q, top_k=pool) or []
        except Exception:
            hits = []
        if hits:
            rank_lists.append(hits)
    if not rank_lists:
        return []
    fused = rrf_fuse(*rank_lists, top_k=pool) if len(rank_lists) > 1 else rank_lists[0][:pool]
    ranked = rerank_hits(queries[0], fused, top_n=k)
    return [
        {
            "source": h.get("source"),
            "score": h.get("score"),
            "text": (h.get("text") or "")[:800],
            "reranked": bool(h.get("reranked")),
        }
        for h in ranked
        if (h.get("text") or "").strip()
    ]


def retrieve_for_dialog(question: str, history: list[dict] | None = None, top_k: int = 5) -> dict[str, Any]:
    queries = expand_retrieval_queries(question, history)
    primary = queries[0] if queries else (question or "")
    sources = retrieve_knowledge(primary, top_k=top_k, extra_queries=queries[1:])
    memories = search_memories(primary, top_k=min(4, top_k))
    return {
        "queries": queries,
        "sources": sources,
        "memories": [
            {
                "id": m.get("id"),
                "kind": m.get("kind"),
                "code": m.get("code"),
                "title": m.get("title"),
                "content": m.get("content"),
                "score": m.get("_score"),
            }
            for m in memories
        ],
        "rerank": rerank_info(),
    }


def format_retrieval_block(bundle: dict[str, Any]) -> str:
    lines = ["### 已检索到的纪律（请优先引用；未出现的条款视为未知，不要编造）"]
    sources = bundle.get("sources") or []
    if not sources:
        lines.append("（无命中。纪律类问题请再调 search_knowledge，或明确说未知。）")
    else:
        for i, h in enumerate(sources, start=1):
            src = h.get("source") or "unknown"
            text = (h.get("text") or "").strip().replace("\n", " ")
            lines.append(f"[{i}] {src}\n{text}")
    mems = bundle.get("memories") or []
    if mems:
        lines.append("\n### 相关沉淀")
        for m in mems:
            title = m.get("title") or m.get("id") or "沉淀"
            content = (m.get("content") or "").strip()
            lines.append(f"- {title}：{content}")
    qs = bundle.get("queries") or []
    if qs:
        lines.append("\n### 检索查询\n- " + " | ".join(qs))
    return "\n".join(lines)


def _history_texts(history: list[dict] | None) -> list[str]:
    out = []
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            out.append(str(h["content"])[:400])
    return out


_PREFIX_STOP = {
    "还能", "持有", "清仓", "减仓", "看看", "怎么", "现在", "今天", "市场", "情绪",
    "纪律", "利空", "门禁", "仓位", "加仓", "先看", "一下", "要不要", "什么", "这个",
}


def _guess_names(text: str) -> list[str]:
    blob = text or ""
    out: list[str] = []
    for m in re.findall(r"[\u4e00-\u9fff]{2,4}(?:集团|股份|科技|电子|医药|银行)", blob):
        if m not in out:
            out.append(m)
    try:
        from app.infrastructure.persistence.analyses_store import load_analyses

        known = []
        for a in (load_analyses() or {}).values():
            nm = (a.get("name") or "").strip()
            if nm:
                known.append(nm)
        for row in (market.quote_cache or {}).values():
            nm = (row.get("name") or "").strip()
            if nm:
                known.append(nm)
        for nm in known:
            if not nm or nm in out:
                continue
            if re.fullmatch(r"(?:sh|sz)?\d{5,6}", nm, re.I):
                continue
            prefix = nm[:2]
            if not re.fullmatch(r"[\u4e00-\u9fff]{2}", prefix):
                continue
            if nm in blob or (prefix not in _PREFIX_STOP and prefix in blob):
                out.append(nm)
    except Exception:
        pass
    return out[:4]
