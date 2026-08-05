"""登录 / 会话。"""
from __future__ import annotations

from app.infrastructure.persistence.identity import (
    authenticate,
    create_session,
    destroy_session,
    resolve_session,
)


def public_user(user: dict) -> dict:
    return {
        "account": user.get("account"),
        "displayName": user.get("displayName") or user.get("account"),
        "roles": user.get("roles") or [],
        "permissions": user.get("permissions") or [],
    }


def login(account: str, password: str) -> dict:
    user = authenticate(account, password)
    if not user:
        return {"ok": False, "error": "账号或密码错误"}
    token, expires_at = create_session(user)
    return {
        "ok": True,
        "token": token,
        "expiresAt": expires_at.isoformat(),
        **public_user(user),
    }


def logout(token: str) -> dict:
    destroy_session(token)
    return {"ok": True}


def me(token: str) -> dict:
    user = resolve_session(token)
    if not user:
        return {"ok": False, "authed": False}
    return {"ok": True, "authed": True, **public_user(user)}
