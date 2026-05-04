"""Chat REST : envoyer un message texte, recevoir la réponse LLM."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import current_user

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, user: Annotated[dict, Depends(current_user)]) -> ChatResponse:
    """Délègue à l'orchestrator (qui appellera memory + llm)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "http://orchestrator:8001/orchestrate",
            json={
                "session_id": req.session_id,
                "user_id": user["sub"],
                "is_owner": user.get("is_owner", False),
                "text": req.message,
            },
        )
        r.raise_for_status()
        data = r.json()
    return ChatResponse(reply=data["reply"], session_id=data["session_id"])
