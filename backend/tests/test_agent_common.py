from __future__ import annotations

from app.agents.common import add_code_intent, extract_typed_json


def test_extract_strategy_patch_from_fence():
    text = """可以加。
```json
{"type":"strategy_patch","summary":"加工业富联","patches":[{"target":"codes","code":"sh601138","action":"add","payload":{"name":"工业富联"}}]}
```
"""
    patch, mem = extract_typed_json(text)
    assert patch and patch["type"] == "strategy_patch"
    assert patch["patches"][0]["code"] == "sh601138"
    assert mem is None


def test_extract_strategy_patch_bare_json():
    text = (
        '如需写入请采纳：'
        '{"type":"strategy_patch","summary":"加","patches":[{"target":"codes","code":"sh601138","action":"add","payload":{"name":"工业富联"}}]}'
    )
    patch, _ = extract_typed_json(text)
    assert patch is not None
    assert patch["patches"][0]["code"] == "sh601138"


def test_add_code_intent_watchlist_phrases():
    assert add_code_intent("把工业富联加入观察池")
    assert add_code_intent("需要加入自选")
    assert not add_code_intent("工业富联今天怎么样")
