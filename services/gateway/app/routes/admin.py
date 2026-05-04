"""Endpoints admin : gestion users, voiceprint, devices. Owner-only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import require_owner
from ..db import get_pool

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    is_owner: bool = False


@router.get("/users")
async def list_users(user: Annotated[dict, Depends(require_owner)]) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, username, is_owner, created_at FROM users ORDER BY created_at"
        )
    return [
        {**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


@router.post("/users")
async def create_user(
    body: UserCreate, user: Annotated[dict, Depends(require_owner)]
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO users(username, is_owner) VALUES($1, $2) RETURNING id, username, is_owner",
            body.username,
            body.is_owner,
        )
    return {"id": str(row["id"]), "username": row["username"], "is_owner": row["is_owner"]}
