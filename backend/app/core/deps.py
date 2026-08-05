from __future__ import annotations

from fastapi import Header, HTTPException

from app.infrastructure.persistence.identity import has_perm, resolve_session


async def current_user(token: str = Header(default="", alias="x-jarvis-token")) -> dict:
    user = resolve_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


def require_perm(code: str):
    async def dep(token: str = Header(default="", alias="x-jarvis-token")) -> dict:
        user = resolve_session(token)
        if not user:
            raise HTTPException(status_code=401, detail="未登录")
        if not has_perm(user, code):
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return dep
