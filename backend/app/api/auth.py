"""HTTP：登录 / 会话 / 当前用户（MySQL RBAC，无库时回退 .env）。"""
from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.infra.identity import authenticate, create_session, destroy_session, resolve_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _public_user(user: dict) -> dict:
    return {
        "account": user.get("account"),
        "displayName": user.get("displayName") or user.get("account"),
        "roles": user.get("roles") or [],
        "permissions": user.get("permissions") or [],
    }


@router.post("/login")
async def login(body: LoginIn):
    user = authenticate(body.account, body.password)
    if not user:
        return {"ok": False, "error": "账号或密码错误"}
    token, expires_at = create_session(user)
    return {
        "ok": True,
        "token": token,
        "expiresAt": expires_at.isoformat(),
        **_public_user(user),
    }


@router.post("/logout")
async def logout(token: str = Header(default="", alias="x-jarvis-token")):
    destroy_session(token)
    return {"ok": True}


@router.get("/me")
async def me(token: str = Header(default="", alias="x-jarvis-token")):
    user = resolve_session(token)
    if not user:
        return {"ok": False, "authed": False}
    return {"ok": True, "authed": True, **_public_user(user)}
