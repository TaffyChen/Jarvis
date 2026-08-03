from __future__ import annotations

"""Rebuild local knowledge index: python -m app.scripts.reindex_kb"""

from app.config import settings
from app.core.local_kb import Chunk, chunk_markdown, get_store
from app.core.storage import read_json


def main() -> None:
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
            Chunk(
                id=f"analysis:{code}",
                text="\n".join(parts),
                source=f"analyses/{code}",
                meta={"code": code},
            )
        )
    store = get_store()
    store.rebuild(chunks)
    print({"success": True, "chunks": len(chunks), "path": str(store.path)})


if __name__ == "__main__":
    main()
