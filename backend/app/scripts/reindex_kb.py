from __future__ import annotations

"""Rebuild knowledge index: python -m app.scripts.reindex_kb"""

from app.infra.local_kb import rebuild_all


def main() -> None:
    print(rebuild_all())


if __name__ == "__main__":
    main()
