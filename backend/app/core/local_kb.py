"""本地轻量向量库：字符 n-gram TF + 余弦相似度（无外部依赖，后续可替换为 Milvus）。"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from app.config import settings

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]{2,}")


def _tokens(text: str) -> list[str]:
    chars = _TOKEN_RE.findall(text.lower())
    grams: list[str] = []
    # unigrams + bigrams for Chinese chars / words
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
    meta: dict


class LocalVectorStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (settings.vector_dir / "local_kb.json")
        self.chunks: list[Chunk] = []
        self.vocab: dict[str, int] = {}
        self.matrix: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.vocab = raw.get("vocab", {})
        self.chunks = [Chunk(**c) for c in raw.get("chunks", [])]
        vecs = raw.get("vectors", [])
        self.matrix = np.array(vecs, dtype=np.float32) if vecs else None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vocab": self.vocab,
            "chunks": [c.__dict__ for c in self.chunks],
            "vectors": self.matrix.tolist() if self.matrix is not None else [],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _build_vocab(self, docs: Iterable[list[str]]) -> None:
        vocab: dict[str, int] = {}
        for toks in docs:
            for t in toks:
                if t not in vocab:
                    vocab[t] = len(vocab)
        self.vocab = vocab

    def _vectorize(self, toks: list[str]) -> np.ndarray:
        v = np.zeros(len(self.vocab), dtype=np.float32)
        if not self.vocab:
            return v
        for t in toks:
            i = self.vocab.get(t)
            if i is not None:
                v[i] += 1.0
        n = np.linalg.norm(v)
        if n > 0:
            v /= n
        return v

    def rebuild(self, chunks: list[Chunk]) -> None:
        tokenized = [_tokens(c.text) for c in chunks]
        self._build_vocab(tokenized)
        self.chunks = chunks
        if not chunks:
            self.matrix = None
            self.save()
            return
        self.matrix = np.vstack([self._vectorize(t) for t in tokenized])
        self.save()

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.chunks or self.matrix is None or self.matrix.size == 0:
            return []
        q = self._vectorize(_tokens(query))
        if float(np.linalg.norm(q)) == 0:
            return []
        scores = self.matrix @ q
        idx = np.argsort(-scores)[:top_k]
        out = []
        for i in idx:
            sc = float(scores[int(i)])
            if sc <= 0:
                continue
            c = self.chunks[int(i)]
            out.append(
                {
                    "id": c.id,
                    "text": c.text,
                    "source": c.source,
                    "meta": c.meta,
                    "score": round(sc, 4),
                }
            )
        return out


def chunk_markdown(text: str, source: str, max_len: int = 400) -> list[Chunk]:
    parts = re.split(r"\n#{1,3}\s+", text)
    chunks: list[Chunk] = []
    n = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        for i in range(0, len(part), max_len):
            piece = part[i : i + max_len].strip()
            if len(piece) < 20:
                continue
            n += 1
            chunks.append(
                Chunk(
                    id=f"{source}#{n}",
                    text=piece,
                    source=source,
                    meta={"offset": i},
                )
            )
    return chunks


_store: LocalVectorStore | None = None


def get_store() -> LocalVectorStore:
    global _store
    if _store is None:
        _store = LocalVectorStore()
    return _store
