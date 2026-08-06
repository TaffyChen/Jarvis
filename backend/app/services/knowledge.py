"""知识库文档维护（读写 knowledge/*.md）。"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.infrastructure.kb.chunk import chunk_markdown
from app.infrastructure.kb.extract import SUPPORTED_UPLOAD_EXTS, extract_markdown, md_path_for_upload
from app.infrastructure.kb.index import collect_chunks, kb_info, rebuild_all
from app.services.rag import retrieve_knowledge
from app.services.rag import retrieve_knowledge


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


def upload_kb_document(
    filename: str = "",
    data: bytes | None = None,
    content_base64: str | None = None,
    source_path: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """上传通用文件，抽成 Markdown 后写入 knowledge/。"""
    raw = data
    name = (filename or "").strip()
    if source_path:
        src = Path(source_path).expanduser().resolve()
        if not src.is_file():
            raise ValueError("源文件不存在")
        raw = src.read_bytes()
        name = name or src.name
    elif content_base64:
        try:
            raw = base64.b64decode(content_base64, validate=False)
        except Exception as exc:
            raise ValueError("content_base64 无效") from exc
    if raw is None:
        raise ValueError("需要文件内容、content_base64 或 source_path")
    if not name:
        raise ValueError("需要文件名")
    limit = max(1, int(settings.kb_upload_max_mb or 8)) * 1024 * 1024
    if len(raw) > limit:
        raise ValueError(f"文件超过 {settings.kb_upload_max_mb}MB 上限")
    markdown = extract_markdown(name, raw)
    rel = md_path_for_upload(name)
    result = save_kb_document(rel, markdown, create=not overwrite)
    result["originalName"] = Path(name).name
    result["extractedChars"] = len(markdown)
    return result


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
    info["upload"] = {
        "maxMb": int(settings.kb_upload_max_mb or 8),
        "extensions": list(SUPPORTED_UPLOAD_EXTS),
    }
    return info


def reindex_knowledge() -> dict[str, Any]:
    return rebuild_all()


def search_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve_knowledge(query or "", top_k=top_k)
