"""本地账户 + RBAC（MySQL）。无库时回退到 .env 单账号。"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.infra.storage import mysql_conn, mysql_enabled

PBKDF2_ITERS = 200_000

ROLES = (
    ("admin", "管理员", "全部权限"),
    ("member", "成员", "日常看盘与持仓，不含用户管理/知识库维护"),
)

PERMISSIONS = (
    ("data.read", "读取数据", "行情、持仓、分析只读"),
    ("data.write", "写入数据", "改持仓、标的、日记、分析"),
    ("chat.use", "对话", "使用 Jarvis 对话"),
    ("kb.manage", "维护知识库", "编辑 knowledge/*.md 并预览切块"),
    ("kb.reindex", "重建知识库", "重建向量索引"),
    ("user.manage", "用户管理", "管理账号与角色"),
)

ROLE_PERMS = {
    "admin": ("data.read", "data.write", "chat.use", "kb.manage", "kb.reindex", "user.manage"),
    "member": ("data.read", "data.write", "chat.use"),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, hash_b64 = (stored or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return secrets.compare_digest(dk, expected)
    except Exception:
        return False


def init_identity() -> dict[str, Any]:
    if not mysql_enabled():
        return {"backend": "env", "seeded": False}
    conn = mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              code VARCHAR(64) NOT NULL UNIQUE,
              name VARCHAR(64) NOT NULL,
              description VARCHAR(255) NOT NULL DEFAULT '',
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              code VARCHAR(64) NOT NULL UNIQUE,
              name VARCHAR(64) NOT NULL,
              description VARCHAR(255) NOT NULL DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
              role_id BIGINT NOT NULL,
              permission_id BIGINT NOT NULL,
              PRIMARY KEY (role_id, permission_id),
              CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id),
              CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id BIGINT PRIMARY KEY AUTO_INCREMENT,
              account VARCHAR(64) NOT NULL UNIQUE,
              password_hash VARCHAR(255) NOT NULL,
              display_name VARCHAR(64) NOT NULL DEFAULT '',
              status TINYINT NOT NULL DEFAULT 1,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_roles (
              user_id BIGINT NOT NULL,
              role_id BIGINT NOT NULL,
              PRIMARY KEY (user_id, role_id),
              CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users(id),
              CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES roles(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
              token VARCHAR(128) PRIMARY KEY,
              user_id BIGINT NOT NULL,
              expires_at DATETIME NOT NULL,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              CONSTRAINT fk_sess_user FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        for code, name, desc in ROLES:
            cur.execute(
                "INSERT IGNORE INTO roles (code, name, description) VALUES (%s, %s, %s)",
                (code, name, desc),
            )
        for code, name, desc in PERMISSIONS:
            cur.execute(
                "INSERT IGNORE INTO permissions (code, name, description) VALUES (%s, %s, %s)",
                (code, name, desc),
            )
        cur.execute("SELECT id, code FROM roles")
        role_ids = {r["code"]: r["id"] for r in cur.fetchall()}
        cur.execute("SELECT id, code FROM permissions")
        perm_ids = {p["code"]: p["id"] for p in cur.fetchall()}
        for role_code, perms in ROLE_PERMS.items():
            rid = role_ids[role_code]
            for pcode in perms:
                cur.execute(
                    "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                    (rid, perm_ids[pcode]),
                )

        account = (settings.auth_account or "jarvis").strip() or "jarvis"
        cur.execute("SELECT id FROM users WHERE account = %s", (account,))
        row = cur.fetchone()
        created_user = False
        if not row:
            cur.execute(
                """
                INSERT INTO users (account, password_hash, display_name, status)
                VALUES (%s, %s, %s, 1)
                """,
                (account, hash_password(settings.auth_password or "admin"), "Jarvis"),
            )
            uid = cur.lastrowid
            created_user = True
        else:
            uid = row["id"]
        cur.execute(
            "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (uid, role_ids["admin"]),
        )
    return {"backend": "mysql", "seeded": True, "adminAccount": account, "createdUser": created_user}


def _load_user_row(cur, user_id: int) -> dict[str, Any] | None:
    cur.execute(
        "SELECT id, account, display_name, status FROM users WHERE id = %s",
        (user_id,),
    )
    user = cur.fetchone()
    if not user:
        return None
    cur.execute(
        """
        SELECT r.code, r.name
        FROM roles r
        JOIN user_roles ur ON ur.role_id = r.id
        WHERE ur.user_id = %s
        ORDER BY r.id
        """,
        (user_id,),
    )
    roles = [{"code": r["code"], "name": r["name"]} for r in cur.fetchall()]
    cur.execute(
        """
        SELECT DISTINCT p.code
        FROM permissions p
        JOIN role_permissions rp ON rp.permission_id = p.id
        JOIN user_roles ur ON ur.role_id = rp.role_id
        WHERE ur.user_id = %s
        """,
        (user_id,),
    )
    perms = sorted(r["code"] for r in cur.fetchall())
    return {
        "id": user["id"],
        "account": user["account"],
        "displayName": user["display_name"] or user["account"],
        "status": int(user["status"]),
        "roles": roles,
        "permissions": perms,
    }


def _env_admin_user() -> dict[str, Any]:
    return {
        "id": 0,
        "account": settings.auth_account,
        "displayName": settings.auth_account,
        "status": 1,
        "roles": [{"code": "admin", "name": "管理员"}],
        "permissions": [p[0] for p in PERMISSIONS],
    }


def authenticate(account: str, password: str) -> dict[str, Any] | None:
    account = (account or "").strip()
    if not account or not password:
        return None
    if not mysql_enabled():
        if account == settings.auth_account and password == settings.auth_password:
            return _env_admin_user()
        return None
    conn = mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, password_hash, status FROM users WHERE account = %s",
            (account,),
        )
        row = cur.fetchone()
        if not row or int(row["status"]) != 1:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return _load_user_row(cur, row["id"])


def create_session(user: dict[str, Any]) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(24)
    expires_at = _now() + timedelta(hours=max(1, int(settings.auth_token_ttl_hours or 24)))
    if not mysql_enabled() or not user.get("id"):
        _MEM_SESSIONS[token] = {"user": user, "expiresAt": expires_at}
        return token, expires_at
    conn = mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM auth_sessions WHERE expires_at <= UTC_TIMESTAMP()")
        cur.execute(
            "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user["id"], expires_at.replace(tzinfo=None)),
        )
    return token, expires_at


def resolve_session(token: str) -> dict[str, Any] | None:
    token = (token or "").strip()
    if not token:
        return None
    if token in _MEM_SESSIONS:
        s = _MEM_SESSIONS[token]
        if s["expiresAt"] <= _now():
            _MEM_SESSIONS.pop(token, None)
            return None
        return s["user"]
    if not mysql_enabled():
        return None
    conn = mysql_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, expires_at FROM auth_sessions
            WHERE token = %s
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return None
        exp = row["expires_at"]
        if getattr(exp, "tzinfo", None) is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now():
            cur.execute("DELETE FROM auth_sessions WHERE token = %s", (token,))
            return None
        user = _load_user_row(cur, row["user_id"])
        if not user or user["status"] != 1:
            return None
        return user


def destroy_session(token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    _MEM_SESSIONS.pop(token, None)
    if not mysql_enabled():
        return
    conn = mysql_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM auth_sessions WHERE token = %s", (token,))


def has_perm(user: dict[str, Any] | None, code: str) -> bool:
    if not user:
        return False
    roles = {r["code"] for r in (user.get("roles") or [])}
    if "admin" in roles:
        return True
    return code in set(user.get("permissions") or [])


_MEM_SESSIONS: dict[str, dict[str, Any]] = {}
