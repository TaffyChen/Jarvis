"""HTTP：共用能力发现与调用（多 Agent / 脚本）。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.capabilities import list_capabilities
from app.infra.market.service import market

router = APIRouter(prefix="/api/jarvis", tags=["capabilities"])


class CapabilityInvokeIn(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)


@router.get("/capabilities")
async def capabilities():
    return {"capabilities": list_capabilities()}


@router.post("/capabilities/invoke")
async def capabilities_invoke(body: CapabilityInvokeIn):
    from app.capabilities.registry import invoke

    try:
        result = invoke(body.name, **(body.arguments or {}))
    except KeyError as e:
        return {"success": False, "error": str(e)}
    except TypeError as e:
        return {"success": False, "error": f"bad_args:{e}"}
    if isinstance(result, dict) and result.get("need_quotes"):
        asyncio.create_task(market.fetch_all_quotes())
        asyncio.create_task(market.fetch_all_klines())
    return {"success": True, "name": body.name, "result": result}
