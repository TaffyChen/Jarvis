"""知识库门面：收集切块、选择 local/milvus 存储、重建索引。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.infra.kb_chunk import Chunk, chunk_markdown, chunk_plain
from app.infra.kb_embed import embed_query, embed_texts, embedding_info
from app.infra.kb_rerank import rerank_info
from app.infra.kb_search import keyword_rank, rrf_fuse


def _meta_path() -> Path:
    return settings.vector_dir / "kb_meta.json"


def write_kb_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "vectorBackend": kb_backend(),
        "embedding": embedding_info(),
        "chunkStrategy": "markdown-section-window+overlap",
    }
    if extra:
        payload.update(extra)
    _meta_path().parent.mkdir(parents=True, exist_ok=True)
    _meta_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def read_kb_meta() -> dict[str, Any]:
    p = _meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


class LocalVectorStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (settings.vector_dir / "local_kb.json")
        self.chunks: list[Chunk] = []
        self.matrix: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.chunks = [Chunk(**c) for c in raw.get("chunks", [])]
        vecs = raw.get("vectors", [])
        self.matrix = np.array(vecs, dtype=np.float32) if vecs else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "embedding": embedding_info(),
            "chunks": [c.__dict__ for c in self.chunks],
            "vectors": self.matrix.tolist() if self.matrix is not None else [],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def rebuild(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        if not chunks:
            self.matrix = None
            self.save()
            return
        vecs = embed_texts([c.text for c in chunks])
        self.matrix = np.array(vecs, dtype=np.float32)
        self.save()

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
        vector_hits = []
        rows = []
        for i, c in enumerate(self.chunks):
            row = {"id": c.id, "text": c.text, "source": c.source, "meta": c.meta}
            rows.append(row)
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
        kw_hits = keyword_rank(query, rows, top_k=20)
        return rrf_fuse(vector_hits, kw_hits, top_k=top_k)


_store = None


def kb_backend() -> str:
    return (settings.vector_backend or "local").strip().lower() or "local"


def reset_store() -> None:
    global _store
    _store = None


def get_store():
    global _store
    if _store is None:
        if kb_backend() == "milvus":
            from app.infra.milvus_kb import MilvusVectorStore

            _store = MilvusVectorStore()
        else:
            _store = LocalVectorStore()
    return _store


def collect_chunks() -> list[Chunk]:
    from app.domain.memory import memories_as_chunks
    from app.infra.storage import read_json

    chunks: list[Chunk] = []
    for p in sorted(settings.knowledge_dir.glob("**/*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(chunk_markdown(text, source=str(p.relative_to(settings.knowledge_dir))))
    analyses = read_json("analyses.json", {})
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
    for m in memories_as_chunks():
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
    }
    try:
        store = get_store()
        info["ready"] = bool(store.has_data())
        info["path"] = str(store.path)
    except Exception as e:
        info["ready"] = False
        info["error"] = str(e)
    if backend == "milvus":
        info["uri"] = settings.milvus_uri
        info["collection"] = settings.milvus_collection
    return info


def ensure_kb_ready() -> dict:
    if kb_backend() != "milvus":
        return {"backend": "local", "action": "skip"}
    try:
        store = get_store()
        if store.has_data():
            return {"backend": "milvus", "action": "ready", "path": str(store.path)}
        result = rebuild_all()
        result["action"] = "indexed"
        return result
    except Exception as e:
        return {"backend": "milvus", "action": "error", "error": str(e)}
