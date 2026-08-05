"""股票/ETF 代码规范化（与前端 AddStockDialog 规则一致）。"""
from __future__ import annotations

import re


def normalize_code(raw: str | None) -> str:
    """600693 / sh600693 / SZ000636 → sh600693 / sz000636。"""
    c = str(raw or "").strip().lower()
    c = re.sub(r"^(sh|sz)", "", c)
    c = re.sub(r"\D", "", c)  # 只留数字
    if not c:
        return ""
    # 上海：6/5/9 开头，或 11/12 开头（转债等）
    if c.startswith(("5", "6", "9")) or c.startswith(("11", "12")):
        return "sh" + c
    return "sz" + c


def looks_like_code(raw: str | None) -> bool:
    digits = re.sub(r"\D", "", str(raw or ""))
    return len(digits) in (5, 6)
