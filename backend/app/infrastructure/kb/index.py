"""知识库索引门面：切块收集 + Milvus 存储（pytest 用内存索引）。"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.core.config import settings
from app.infrastructure.persistence import storage
from app.infrastructure.kb.chunk import Chunk, chunk_markdown, chunk_plain
from app.infrastructure.kb.embed import embed_query, embed_texts, embedding_info
from app.infrastructure.kb.rerank import rerank_info
from app.infrastructure.kb.search import keyword_rank, rrf_fuse


class InMemoryVectorStore:
    """仅单测使用，不落盘。"""

    def __init__(self):
        self.chunks: list[Chunk] = []
        self.matrix: np.ndarray | None = None

    @property
    def path(self) -> str:
        return "memory://kb"

    def rebuild(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        if not chunks:
            self.matrix = None
            return
        vecs = embed_texts([c.text for c in chunks])
        self.matrix = np.array(vecs, dtype=np.float32)

    def has_data(self) -> bool:
        return bool(self.chunks and self.matrix is not None and self.matrix.size > 0)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.chunks or self.matrix is None or self.matrix.size == 0:
            return []
        q = np.array(embed_query(query), dtype=np.float32)
        n = float(np.linalg.norm(q))
        if n == 0:
            return []
        q /= n
        mat = self.matrix.copy()
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1
        mat = mat / norms
        scores = mat @ q
        idx = np.argsort(-scores)[: max(20, int(top_k) * 4)]
        rows = [{"id": c.id, "text": c.text, "source": c.source, "meta": c.meta} for c in self.chunks]
        vector_hits = []
        for i in idx:
            sc = float(scores[int(i)])
            if sc <= 0:
                continue
            c = self.chunks[int(i)]
            vector_hits.append({
                "id": c.id,
                "text": c.text,
                "source": c.source,
                "meta": c.meta,
                "score": round(sc, 4),
            })
        return rrf_fuse(vector_hits, keyword_rank(query, rows, top_k=20), top_k=top_k)


def write_kb_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "vectorBackend": "milvus",
        "embedding": embedding_info(),
        "chunkStrategy": "markdown-section-window+overlap",
    }
    if extra:
        payload.update(extra)
    if storage.mysql_enabled():
        storage._mysql_write("kb_meta", payload)  # noqa: SLF001
    elif storage.memory_mode():
        storage.memory_blob()["kb_meta"] = payload
    else:
        storage.require_mysql()
    return payload


def read_kb_meta() -> dict[str, Any]:
    if storage.mysql_enabled():
        try:
            val = storage._mysql_read("kb_meta")  # noqa: SLF001
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}
    if storage.memory_mode():
        meta = storage.memory_blob().get("kb_meta") or {}
        return meta if isinstance(meta, dict) else {}
    return {}


_store = None


def kb_backend() -> str:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return "memory"
    return "milvus"


def reset_store() -> None:
    global _store
    _store = None


def get_store():
    global _store
    if _store is None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            _store = InMemoryVectorStore()
        else:
            from app.infrastructure.kb.milvus import MilvusVectorStore

            _store = MilvusVectorStore()
    return _store


def collect_chunks() -> list[Chunk]:
    from app.domain.memory import memories_to_chunks
    from app.infrastructure.persistence.analyses_store import load_analyses
    from app.infrastructure.persistence.memory_store import load_memories

    chunks: list[Chunk] = []
    for p in sorted(settings.knowledge_dir.glob("**/*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(chunk_markdown(text, source=str(p.relative_to(settings.knowledge_dir))))
    analyses = load_analyses()
    for code, a in (analyses or {}).items():
        parts = [
            a.get("name") or code,
            a.get("reason") or "",
            a.get("notes") or "",
            " ".join(x.get("text") or "" for x in (a.get("analysis") or [])),
            f"riskOk={a.get('riskOk')} reviewedAt={a.get('reviewedAt')}",
        ]
        chunks.append(
            chunk_plain(
                "\n".join(parts),
                source=f"analyses/{code}",
                chunk_id=f"analysis:{code}",
                meta={"kind": "analysis", "code": code},
            )
        )
    for m in memories_to_chunks(load_memories() or []):
        chunks.append(
            chunk_plain(
                m["text"],
                source=m["source"],
                chunk_id=m["id"],
                meta=m.get("meta") or {"kind": "memory"},
            )
        )
    return [c for c in chunks if (c.text or "").strip()]


def rebuild_all() -> dict:
    chunks = collect_chunks()
    store = get_store()
    store.rebuild(chunks)
    meta = write_kb_meta({"chunks": len(chunks), "path": str(getattr(store, "path", ""))})
    return {
        "success": True,
        "chunks": len(chunks),
        "backend": kb_backend(),
        "path": str(getattr(store, "path", "")),
        "embedding": meta.get("embedding"),
        "updatedAt": meta.get("updatedAt"),
    }


def kb_info() -> dict:
    backend = kb_backend()
    meta = read_kb_meta()
    info: dict = {
        "backend": backend,
        "embedding": embedding_info(),
        "rerank": rerank_info(),
        "chunkStrategy": meta.get("chunkStrategy") or "markdown-section-window+overlap",
        "updatedAt": meta.get("updatedAt"),
        "chunks": meta.get("chunks"),
        "uri": settings.milvus_uri,
        "collection": settings.milvus_collection,
    }
    try:
        store = get_store()
        info["ready"] = bool(store.has_data())
        info["path"] = str(store.path)
    except Exception as e:
        info["ready"] = False
        info["error"] = str(e)
    return info


def ensure_kb_ready() -> dict:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"backend": "memory", "action": "skip"}
    try:
        store = get_store()
        if store.has_data():
            return {"backend": "milvus", "action": "ready", "path": str(store.path)}
        result = rebuild_all()
        result["action"] = "indexed"
        return result
    except Exception as e:
        return {"backend": "milvus", "action": "error", "error": str(e)}
