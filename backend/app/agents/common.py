"""Agent 共用解析工具。"""
from __future__ import annotations

import json
import re


def extract_typed_json(text: str) -> tuple[dict | None, dict | None]:
    """从回答中提取 strategy_patch 与 memory_patch（可各一个）。

    优先 ```json``` 代码块；其次扫描裸 JSON 对象（模型偶发不包 fence）。
    """
    strategy = None
    memory = None
    raw = text or ""

    for m in re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, re.I):
        obj = _safe_obj(m.group(1))
        if not obj:
            continue
        t = obj.get("type")
        if t == "strategy_patch":
            strategy = obj
        elif t == "memory_patch":
            memory = obj

    if strategy is None or memory is None:
        for obj in _iter_json_objects(raw):
            t = obj.get("type")
            if t == "strategy_patch" and strategy is None:
                strategy = obj
            elif t == "memory_patch" and memory is None:
                memory = obj
            if strategy is not None and memory is not None:
                break

    return strategy, memory


def _safe_obj(blob: str) -> dict | None:
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _iter_json_objects(text: str):
    """粗扫含 "type" 的花括号对象，供无 fence 时兜底。"""
    for m in re.finditer(r"\{\s*\"type\"\s*:", text or ""):
        start = m.start()
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj = _safe_obj(text[start : i + 1])
                    if obj:
                        yield obj
                    break


def remember_intent(question: str) -> bool:
    q = question or ""
    keys = ("记住", "记下", "沉淀", "记一下", "记着", "别忘了")
    return any(k in q for k in keys)


def add_code_intent(question: str) -> bool:
    """用户想把股票加入观察池/自选。"""
    q = question or ""
    keys = (
        "添加标的",
        "加入自选",
        "加自选",
        "加个标的",
        "加标的",
        "关注一下",
        "帮我添加",
        "帮我加",
        "加入观察池",
        "加观察池",
        "加到观察池",
        "放进观察池",
        "观察池加",
        "加到自选",
        "放进自选",
        "加入自选池",
        "需要加入",
        "帮我关注",
        "跟踪一下",
    )
    if any(k in q for k in keys):
        return True
    # 「把工业富联加进来 / 加一下 XXX」口语
    if ("观察池" in q or "自选" in q) and any(k in q for k in ("加", "加入", "添加", "放进")):
        return True
    return False


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


def answer_promises_patch_without_json(answer: str, has_patch: bool) -> bool:
    """回答口头承诺补丁/采纳，但未解析出 strategy_patch。"""
    if has_patch:
        return False
    text = answer or ""
    cues = ("采纳", "补丁", "strategy_patch", "写入观察池", "加入观察池", "点「采纳」", "点“采纳”")
    return any(c in text for c in cues)
