from app.services.rag import expand_retrieval_queries, format_retrieval_block


def test_expand_queries_keeps_original():
    qs = expand_retrieval_queries("三环还能持有吗？")
    assert qs[0] == "三环还能持有吗？"
    assert any("持仓预警" in q or "五灯" in q for q in qs)


def test_expand_queries_uses_history_code():
    qs = expand_retrieval_queries(
        "还能拿吗",
        history=[{"role": "user", "content": "看看 sz300408"}, {"role": "assistant", "content": "先看利空门禁"}],
    )
    blob = " ".join(qs)
    assert "还能拿吗" in blob
    assert "sz300408" in blob or "300408" in blob
    assert "看看" not in blob
    assert "三环还 " not in blob + " "


def test_format_retrieval_block_includes_sources():
    text = format_retrieval_block(
        {
            "queries": ["五灯仓位"],
            "sources": [{"source": "五灯仓位.md", "text": "按灯加减仓", "score": 0.9}],
            "memories": [],
        }
    )
    assert "[1] 五灯仓位.md" in text
    assert "按灯加减仓" in text
    assert "五灯仓位" in text
