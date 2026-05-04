"""Routes sécurité : état Argus, silence (gated owner JWT + voix-print)."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import current_user, require_owner

router = APIRouter()


class SilenceRequest(BaseModel):
    duration_minutes: int = 30
    voice_session_id: str | None = None  # gating voix-print optionnel


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
    """Owner-only (JWT). Si `voice_session_id` est fourni, on demande
    à l'orchestrator si la voix de cette session est confirmée comme owner.
    """
    if req.voice_session_id:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                "http://orchestrator:8001/identity",
                params={"session_id": req.voice_session_id},
            )
            if r.status_code != 200:
                raise HTTPException(status_code=403, detail="vérification voix indisponible")
            ident = r.json()
            if not ident.get("is_owner") or not ident.get("authenticated"):
                raise HTTPException(status_code=403, detail="voix non confirmée comme owner")

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            "http://security:8003/silence",
            json={"duration_minutes": req.duration_minutes},
        )
        r.raise_for_status()
    return r.json()
