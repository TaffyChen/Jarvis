"""知识库文档维护（读写 knowledge/*.md）。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.infra.kb_chunk import chunk_markdown
from app.infra.local_kb import collect_chunks, kb_info, rebuild_all


def _root() -> Path:
    return settings.knowledge_dir.resolve()


def _safe_md_path(rel: str) -> Path:
    rel = (rel or "").replace("\\", "/").strip().lstrip("/")
    if not rel or not rel.endswith(".md"):
        raise ValueError("只允许 .md 文件")
    if any(p in ("", ".", "..") for p in rel.split("/")):
        raise ValueError("非法路径")
    full = (_root() / rel).resolve()
    if full != _root() and _root() not in full.parents:
        raise ValueError("超出知识库目录")
    return full


def list_kb_documents() -> list[dict[str, Any]]:
    root = _root()
    rows = []
    for p in sorted(root.glob("**/*.md")):
        rel = str(p.relative_to(root)).replace("\\", "/")
        st = p.stat()
        rows.append({
            "path": rel,
            "name": p.stem,
            "bytes": st.st_size,
            "updatedAt": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        })
    return rows


def get_kb_document(path: str) -> dict[str, Any]:
    p = _safe_md_path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    text = p.read_text(encoding="utf-8")
    return {"path": path.replace("\\", "/"), "content": text, "bytes": len(text.encode("utf-8"))}


def save_kb_document(path: str, content: str, *, create: bool = False) -> dict[str, Any]:
    p = _safe_md_path(path)
    existed = p.exists()
    if existed and create:
        raise FileExistsError(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content if content is not None else "", encoding="utf-8")
    return {"success": True, "path": path.replace("\\", "/"), "created": not existed}


def delete_kb_document(path: str) -> dict[str, Any]:
    p = _safe_md_path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    p.unlink()
    return {"success": True, "path": path.replace("\\", "/"), "deleted": True}


def preview_kb_chunks(path: str | None = None, content: str | None = None) -> dict[str, Any]:
    if content is None:
        if not path:
            raise ValueError("需要 path 或 content")
        content = get_kb_document(path)["content"]
        source = path
    else:
        source = path or "preview.md"
    chunks = chunk_markdown(content, source=source)
    return {
        "source": source,
        "chunks": [
            {"id": c.id, "text": c.text, "meta": c.meta}
            for c in chunks
        ],
        "count": len(chunks),
    }


def kb_overview() -> dict[str, Any]:
    info = kb_info()
    docs = list_kb_documents()
    info["documents"] = docs
    info["collectedChunks"] = len(collect_chunks())
    indexed_at = info.get("updatedAt") or ""
    info["needsReindex"] = bool(
        indexed_at and any((d.get("updatedAt") or "") > indexed_at for d in docs)
    ) or not info.get("ready")
    return info


def reindex_knowledge() -> dict[str, Any]:
    return rebuild_all()
