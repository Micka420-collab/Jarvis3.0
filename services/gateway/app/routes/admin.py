"""Endpoints admin : gestion users, voiceprint, devices. Owner-only."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_owner
from ..db import get_pool

router = APIRouter()

Role = Literal["owner", "adult", "teen", "child", "guest"]


class UserCreate(BaseModel):
    username: str
    display_name: str | None = None
    is_owner: bool = False
    role: Role = "adult"
    permissions: dict = {}


class UserUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    role: Role | None = None
    permissions: dict | None = None
    is_owner: bool | None = None


@router.get("/users")
async def list_users(user: Annotated[dict, Depends(require_owner)]) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, display_name, avatar_url, is_owner, role,
                   permissions, voice_enrolled, face_enrolled, created_at
              FROM users
          ORDER BY is_owner DESC, created_at
            """
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
    role = "owner" if body.is_owner else body.role
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users(username, display_name, is_owner, role, permissions)
            VALUES($1, $2, $3, $4, $5::jsonb)
            RETURNING id, username, display_name, is_owner, role
            """,
            body.username,
            body.display_name or body.username,
            body.is_owner,
            role,
            json.dumps(body.permissions),
        )
    return {**dict(row), "id": str(row["id"])}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str, body: UserUpdate, user: Annotated[dict, Depends(require_owner)]
) -> dict:
    pool = await get_pool()
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="aucun champ à modifier")
    sets: list[str] = []
    values: list = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        if k == "permissions":
            sets.append(f"permissions = ${i}::jsonb")
            values.append(json.dumps(v))
        else:
            sets.append(f"{k} = ${i}")
            values.append(v)
    values.append(user_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ${len(values)} RETURNING id, username, role",
            *values,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="user inconnu")
    return {**dict(row), "id": str(row["id"])}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str, user: Annotated[dict, Depends(require_owner)]
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        out = await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    return {"deleted": out.split()[-1]}
