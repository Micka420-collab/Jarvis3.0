"""Pilotage IoT direct depuis l'UI (sans LLM). Gating owner pour les actions sensibles."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import current_user, require_owner
from ..db import get_pool

router = APIRouter()


class DeviceCommand(BaseModel):
    device_id: str
    action: str
    params: dict = {}


@router.get("/devices")
async def list_devices(user: Annotated[dict, Depends(current_user)]) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, transport, requires_admin FROM devices ORDER BY name"
        )
    return [dict(r) for r in rows]


@router.post("/command")
async def command(
    cmd: DeviceCommand, user: Annotated[dict, Depends(current_user)]
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        dev = await conn.fetchrow(
            "SELECT requires_admin FROM devices WHERE id = $1", cmd.device_id
        )
    if dev is None:
        raise HTTPException(status_code=404, detail="device inconnu")
    if dev["requires_admin"] and not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="action admin réservée à l'owner")

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            "http://iot:8002/command",
            json=cmd.model_dump(),
        )
        r.raise_for_status()
    return {"status": "queued"}
