"""
LangGraph 多工具决策图 · 状态定义
================================
图在节点之间流转时，靠「一份共享状态」传递数据。
每个节点函数只返回「要更新的字段」；LangGraph 会把它们合并进 GraphState。

阅读提示：先看字段含义，再对照 graph.py 里谁写入、谁读取。
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """决策图的共享状态（TypedDict，运行时就是普通 dict）。

    total=False 表示字段都是可选的：不同节点只会更新自己关心的部分。
    """

    # —— 输入 ——
    question: str
    """本轮用户原话，例如「三环还能持有吗」。"""

    history: list[dict]
    """前端传来的近期对话 [{role, content}, ...]，bootstrap 时截取最近几条。"""

    # —— 对话上下文（给 LLM 看的 OpenAI messages） ——
    messages: list[dict]
    """标准 Chat messages：system / user / assistant / tool。
    agent 往里追加 assistant（可能带 tool_calls）；
    tools 往里追加 role=tool 的执行结果。
    """

    # —— 编排控制 ——
    tool_rounds: int
    """已经完整执行过几轮工具。用于限制最大轮次、强制收束。"""

    tool_trace: list[dict]
    """可观测性：每调用一次工具追加一条
    {tool, args, resultPreview}，最终作为 toolTrace 返回前端。
    """

    # —— 给前端/落盘的引用信息 ——
    retrieve_queries: list[str]
    """本轮 RAG 实际使用的检索查询（含会话扩展）。"""

    sources: list[dict]
    """知识库命中片段（预检索 + search_knowledge 回填）。"""

    memories_used: list[dict]
    """对话沉淀命中（预检索 + search_memory 回填）。"""

    # —— 输出 ——
    answer: str
    """最终自然语言回答（无 tool_calls 的那一轮 assistant content）。"""

    patch: Optional[dict]
    """从 answer 里解析出的 strategy_patch（提案，未自动写库）。"""

    memory_patch: Optional[dict]
    """从 answer 里解析出的 memory_patch（提案，需 HITL 确认）。"""

    model: Optional[str]
    """实际调用的模型名；无 Key 时为 None。"""

    error: Optional[str]
    """预留错误信息字段（当前主路径较少使用）。"""
