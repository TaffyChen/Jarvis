"""知识切块：Markdown 标题路径 + 段落/句子窗口 + overlap（主流 RAG 切法的精简版）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SENT_SPLIT = re.compile(r"(?<=[。！？；!?;\n])")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]{2,}")


def _tokens(text: str) -> list[str]:
    chars = _TOKEN_RE.findall((text or "").lower())
    grams: list[str] = []
    for i, t in enumerate(chars):
        grams.append(t)
        if i + 1 < len(chars):
            grams.append(t + chars[i + 1])
    return grams


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    meta: dict = field(default_factory=dict)


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _window(texts: list[str], chunk_size: int, overlap: int, min_len: int) -> list[str]:
    packed: list[str] = []
    buf = ""
    for part in texts:
        if not part:
            continue
        if len(part) > chunk_size:
            if buf:
                packed.append(buf.strip())
                buf = ""
            for i in range(0, len(part), max(1, chunk_size - overlap)):
                piece = part[i : i + chunk_size].strip()
                if len(piece) >= min_len:
                    packed.append(piece)
            continue
        trial = f"{buf}\n{part}".strip() if buf else part
        if len(trial) <= chunk_size:
            buf = trial
            continue
        if buf.strip():
            packed.append(buf.strip())
        if overlap > 0 and buf:
            tail = buf[-overlap:].lstrip()
            buf = f"{tail}\n{part}".strip() if tail else part
        else:
            buf = part
    if buf.strip() and len(buf.strip()) >= min_len:
        packed.append(buf.strip())
    return packed


def _iter_sections(text: str) -> list[dict]:
    lines = (text or "").replace("\r\n", "\n").split("\n")
    stack: list[tuple[int, str]] = []
    sections: list[dict] = []
    cur_title = ""
    cur_level = 0
    cur_body: list[str] = []

    def flush():
        body = "\n".join(cur_body).strip()
        breadcrumb = " / ".join(t for _, t in stack) or cur_title
        if body or cur_title:
            sections.append({
                "title": cur_title or (stack[-1][1] if stack else ""),
                "level": cur_level,
                "breadcrumb": breadcrumb,
                "body": body,
            })

    for line in lines:
        m = _HEADING.match(line)
        if not m:
            cur_body.append(line)
            continue
        flush()
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        cur_title = title
        cur_level = level
        cur_body = []
    flush()
    if not sections:
        sections.append({"title": "", "level": 0, "breadcrumb": "", "body": (text or "").strip()})
    return sections


def chunk_markdown(
    text: str,
    source: str,
    chunk_size: int = 480,
    overlap: int = 80,
    min_len: int = 24,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    n = 0
    for sec in _iter_sections(text):
        paras = [p.strip() for p in re.split(r"\n\s*\n", sec["body"] or "") if p.strip()]
        units: list[str] = []
        for para in paras:
            if len(para) <= chunk_size:
                units.append(para)
            else:
                units.extend(_split_sentences(para))
        pieces = _window(units, chunk_size=chunk_size, overlap=overlap, min_len=min_len)
        if not pieces and (sec.get("body") or "").strip():
            pieces = [sec["body"].strip()]
        heading = sec.get("breadcrumb") or sec.get("title") or ""
        for i, piece in enumerate(pieces):
            n += 1
            body = f"[{heading}]\n{piece}" if heading else piece
            chunks.append(
                Chunk(
                    id=f"{source}#{n}",
                    text=body,
                    source=source,
                    meta={
                        "kind": "markdown",
                        "heading": heading,
                        "section": sec.get("title") or "",
                        "chunkIndex": i,
                        "strategy": "markdown-section-window",
                    },
                )
            )
    return chunks


def chunk_plain(text: str, source: str, chunk_id: str, meta: dict | None = None) -> Chunk:
    return Chunk(id=chunk_id, text=(text or "").strip(), source=source, meta=meta or {})
