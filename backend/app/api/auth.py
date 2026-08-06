"""HTTP：登录 / 会话 / 当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.services.auth import login as login_svc
from app.services.auth import logout as logout_svc
from app.services.auth import me as me_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login")
async def login(body: LoginIn):
    return login_svc(body.account, body.password)


@router.post("/logout")
async def logout(token: str = Header(default="", alias="x-jarvis-token")):
    return logout_svc(token)


@router.get("/me")
async def me(token: str = Header(default="", alias="x-jarvis-token")):
    return me_svc(token)
