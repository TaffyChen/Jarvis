"""Agent 共用解析工具。"""
from __future__ import annotations

import json
import re


def extract_typed_json(text: str) -> tuple[dict | None, dict | None]:
    """从回答中提取 strategy_patch 与 memory_patch（可各一个）。"""
    strategy = None
    memory = None
    for m in re.finditer(r"```json\s*(\{[\s\S]*?\})\s*```", text or ""):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        t = obj.get("type")
        if t == "strategy_patch":
            strategy = obj
        elif t == "memory_patch":
            memory = obj
    return strategy, memory


def remember_intent(question: str) -> bool:
    q = question or ""
    keys = ("记住", "记下", "沉淀", "记一下", "记着", "别忘了")
    return any(k in q for k in keys)


def add_code_intent(question: str) -> bool:
    """用户想把股票加入观察池/自选。"""
    q = question or ""
    keys = ("添加标的", "加入自选", "加自选", "加个标的", "加标的", "关注一下", "帮我添加", "帮我加")
    return any(k in q for k in keys)


def add_position_intent(question: str) -> bool:
    """用户想写入持仓（成本/股数）。"""
    q = question or ""
    keys = ("添加持仓", "记持仓", "写入持仓", "建仓记录", "加持仓")
    return any(k in q for k in keys)


def remove_position_intent(question: str) -> bool:
    """用户想删除持仓。"""
    q = question or ""
    keys = (
        "删除持仓",
        "删持仓",
        "去掉持仓",
        "移除持仓",
        "清掉持仓",
        "清仓记录",
        "从持仓删",
        "从持仓去掉",
        "不要这个持仓",
        "删掉持仓",
    )
    if any(k in q for k in keys):
        return True
    soft = ("删除", "删掉", "去掉", "移除", "清掉")
    if any(k in q for k in soft) and ("持仓" in q or "仓位" in q):
        return True
    # 「删掉美的集团 / 删除 000333」等口语：排除明显非持仓对象
    if any(k in q for k in soft):
        if any(x in q for x in ("规则", "日记", "记忆", "沉淀", "标的", "自选", "知识")):
            return False
        if "集团" in q or "股份" in q or re.search(r"\d{5,6}", q):
            return True
    return False
