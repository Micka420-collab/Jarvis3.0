"""Endpoint /api/explain : récupère la trace de la dernière action."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import current_user
from ..db import get_pool

router = APIRouter()


class TraceResponse(BaseModel):
    user_text: str | None
    intent: str | None
    tools: list = []
    memory_hits: list = []
    response: str | None
    duration_ms: int | None
    ts: str | None


@router.get("/last", response_model=TraceResponse)
async def explain_last(
    session_id: str, user: Annotated[dict, Depends(current_user)]
) -> TraceResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_text, intent, tools_called, memory_hits, response, duration_ms, ts
              FROM reasoning_traces
             WHERE session_id = $1
          ORDER BY ts DESC
             LIMIT 1
            """,
            session_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="aucune trace pour cette session")
    return TraceResponse(
        user_text=row["user_text"],
        intent=row["intent"],
        tools=row["tools_called"] or [],
        memory_hits=row["memory_hits"] or [],
        response=row["response"],
        duration_ms=row["duration_ms"],
        ts=row["ts"].isoformat(),
    )
