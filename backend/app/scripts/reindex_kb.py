from __future__ import annotations

"""Rebuild knowledge index: python -m app.scripts.reindex_kb"""

from app.infrastructure.kb.index import rebuild_all


def main() -> None:
    print(rebuild_all())


if __name__ == "__main__":
    main()
