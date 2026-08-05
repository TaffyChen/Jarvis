from __future__ import annotations

import pytest

from app.capabilities.knowledge import (
    delete_kb_document,
    get_kb_document,
    list_kb_documents,
    preview_kb_chunks,
    save_kb_document,
)
from app.config import settings
from app.infra.kb_chunk import chunk_markdown
from app.infra.kb_search import keyword_rank, rrf_fuse
from app.infra.local_kb import collect_chunks, reset_store, write_kb_meta


@pytest.fixture()
def isolated_kb(tmp_path, isolated_data_dir):
    old_knowledge = settings.knowledge_dir
    old_vector = settings.vector_dir
    old_backend = settings.vector_backend
    try:
        object.__setattr__(settings, "knowledge_dir", tmp_path / "knowledge")
        object.__setattr__(settings, "vector_dir", tmp_path / "vectordb")
        object.__setattr__(settings, "vector_backend", "local")
        settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
        settings.vector_dir.mkdir(parents=True, exist_ok=True)
        reset_store()
        yield tmp_path
    finally:
        reset_store()
        object.__setattr__(settings, "knowledge_dir", old_knowledge)
        object.__setattr__(settings, "vector_dir", old_vector)
        object.__setattr__(settings, "vector_backend", old_backend)


def test_chunk_markdown_keeps_heading_path():
    text = "# 总则\n\n先看市场情绪。\n\n## 五灯\n\n仓位按五灯加减。第二句补充细节。" * 8
    chunks = chunk_markdown(text, "demo.md", chunk_size=80, overlap=20, min_len=8)
    assert chunks
    assert any("五灯" in (c.meta.get("heading") or "") for c in chunks)
    assert all(c.source == "demo.md" for c in chunks)


def test_rrf_prefers_overlap():
    vector = [
        {"id": "a", "text": "向量命中A", "score": 0.9},
        {"id": "b", "text": "向量命中B", "score": 0.8},
    ]
    keyword = [
        {"id": "b", "text": "关键词命中B", "score": 1.0},
        {"id": "c", "text": "关键词命中C", "score": 0.5},
    ]
    fused = rrf_fuse(vector, keyword, top_k=3)
    assert fused[0]["id"] == "b"


def test_keyword_rank_hits_chinese_bigrams():
    rows = [
        {"id": "1", "text": "主升第一天确认后才加仓", "source": "a.md"},
        {"id": "2", "text": "无关内容", "source": "b.md"},
    ]
    hits = keyword_rank("主升第一天", rows, top_k=2)
    assert hits and hits[0]["id"] == "1"


def test_kb_document_crud(isolated_kb):
    created = save_kb_document("试验规则.md", "# 试验\n\n只做纪律说明。", create=True)
    assert created["created"] is True
    docs = list_kb_documents()
    assert any(d["path"] == "试验规则.md" for d in docs)
    doc = get_kb_document("试验规则.md")
    assert "纪律说明" in doc["content"]
    preview = preview_kb_chunks("试验规则.md")
    assert preview["count"] >= 1
    save_kb_document("试验规则.md", "# 试验\n\n更新后的正文。")
    assert "更新后" in get_kb_document("试验规则.md")["content"]
    with pytest.raises(FileExistsError):
        save_kb_document("试验规则.md", "x", create=True)
    with pytest.raises(ValueError):
        save_kb_document("../escape.md", "x")
    delete_kb_document("试验规则.md")
    assert list_kb_documents() == []


def test_collect_chunks_reads_markdown(isolated_kb):
    (settings.knowledge_dir / "角色.md").write_text("# 角色\n\nJarvis 是交易参谋。", encoding="utf-8")
    chunks = collect_chunks()
    assert any(c.source == "角色.md" for c in chunks)
    meta = write_kb_meta({"chunks": len(chunks)})
    assert meta["embedding"]["backend"] in ("hash", "openai")
