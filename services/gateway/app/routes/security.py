"""Routes sécurité : état Argus, silence, historique alertes."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import current_user, require_owner

router = APIRouter()


class SilenceRequest(BaseModel):
    duration_minutes: int = 30


@router.get("/status")
async def status(user: Annotated[dict, Depends(current_user)]) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get("http://security:8003/status")
            return r.json()
        except Exception as e:
            return {"connected": False, "error": str(e)}


@router.post("/silence")
async def silence(
    req: SilenceRequest, user: Annotated[dict, Depends(require_owner)]
) -> dict:
    """Owner-only : met les annonces vocales d'alerte en pause."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post("http://security:8003/silence", json=req.model_dump())
        r.raise_for_status()
    return r.json()
