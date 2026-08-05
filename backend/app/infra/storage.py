from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

_DOC_NAMES = (
    "stock_codes.json",
    "positions.json",
    "analyses.json",
    "journal.json",
    "memory_notes.json",
    "strategy_proposals.json",
    "conversations.json",
)

_conn = None
_mysql_ready = False


def _path(name: str) -> Path:
    return settings.data_dir / name


def mysql_enabled() -> bool:
    return bool((settings.mysql_host or "").strip() and (settings.mysql_password or "").strip())


def mysql_conn():
    if not mysql_enabled():
        raise RuntimeError("mysql disabled")
    return _get_conn()


def _file_read(name: str, default: Any):
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _file_write(name: str, obj: Any) -> None:
    p = _path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _connect():
    import pymysql

    return pymysql.connect(
        host=settings.mysql_host,
        port=int(settings.mysql_port),
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _get_conn():
    global _conn
    if _conn is None:
        _conn = _connect()
        return _conn
    try:
        _conn.ping(reconnect=True)
        return _conn
    except Exception:
        _conn = _connect()
        return _conn


def reset_storage_state() -> None:
    """测试用：断开缓存连接。"""
    global _conn, _mysql_ready
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
    _conn = None
    _mysql_ready = False


def _mysql_read(name: str):
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT payload FROM kv_docs WHERE doc_name = %s", (name,))
        row = cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except Exception:
        return None


def _mysql_write(name: str, obj: Any) -> None:
    payload = json.dumps(obj, ensure_ascii=False)
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO kv_docs (doc_name, payload)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE payload = VALUES(payload)
            """,
            (name, payload),
        )


def init_storage() -> dict[str, Any]:
    """建表；若 MySQL 为空则从 data/*.json 迁入。"""
    global _mysql_ready
    if not mysql_enabled():
        _mysql_ready = False
        return {"backend": "json", "migrated": []}

    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_docs (
              doc_name VARCHAR(128) NOT NULL PRIMARY KEY,
              payload LONGTEXT NOT NULL,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )

    migrated: list[str] = []
    for name in _DOC_NAMES:
        if _mysql_read(name) is not None:
            continue
        p = _path(name)
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        _mysql_write(name, data)
        migrated.append(name)

    _mysql_ready = True
    return {"backend": "mysql", "migrated": migrated}


def storage_info() -> dict[str, Any]:
    if mysql_enabled():
        return {
            "backend": "mysql",
            "ready": _mysql_ready,
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "database": settings.mysql_database,
            "mirrorJson": bool(settings.mysql_mirror_json),
        }
    return {"backend": "json", "ready": True, "dir": str(settings.data_dir)}


def read_json(name: str, default: Any):
    if mysql_enabled():
        try:
            val = _mysql_read(name)
            if val is not None:
                return val
        except Exception:
            pass
        return _file_read(name, default)
    return _file_read(name, default)


def write_json(name: str, obj: Any) -> None:
    if mysql_enabled():
        _mysql_write(name, obj)
        if settings.mysql_mirror_json:
            _file_write(name, obj)
        return  # 默认不再镜像 JSON；需要备份时用 deploy/mysql/export-data.sh
    _file_write(name, obj)
