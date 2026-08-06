from __future__ import annotations

from app.services.conversations import (
    append_conversation,
    create_chat_session,
    get_chat_session,
    list_chat_sessions,
)


def test_chat_session_roundtrip(isolated_data_dir):
    s = create_chat_session("试会话")
    assert s["id"]
    r1 = append_conversation(
        {"question": "现在持仓有哪些？", "answer": "暂无持仓", "orchestrator": "graph"},
        session_id=s["id"],
    )
    assert r1["sessionId"] == s["id"]
    r2 = append_conversation(
        {"question": "五灯怎么看？", "answer": "0红", "orchestrator": "graph"},
        session_id=s["id"],
    )
    assert r2["sessionId"] == s["id"]

    sessions = list_chat_sessions()
    assert any(x["id"] == s["id"] for x in sessions)

    detail = get_chat_session(s["id"])
    assert detail is not None
    assert len(detail["turns"]) == 2
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_append_auto_creates_session(isolated_data_dir):
    r = append_conversation({"question": "帮我复盘", "answer": "按五段…"})
    assert r["sessionId"]
    detail = get_chat_session(r["sessionId"])
    assert detail["session"]["title"]
    assert "复盘" in detail["session"]["title"] or detail["turns"]
