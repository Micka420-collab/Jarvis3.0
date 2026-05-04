"""Login basique : récupère/crée un user et renvoie un JWT.

Note : l'auth principale est la voix-print (gating commandes admin).
Ce login JWT sert surtout aux requêtes REST/WS du frontend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import create_jwt
from ..config import settings
from ..db import get_pool

router = APIRouter()


class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    is_owner: bool


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    if not req.username:
        raise HTTPException(status_code=400, detail="username vide")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, is_owner FROM users WHERE username = $1", req.username
        )
        if row is None:
            is_owner = req.username == settings.owner_username
            row = await conn.fetchrow(
                "INSERT INTO users(username, is_owner) VALUES($1, $2) RETURNING id, username, is_owner",
                req.username,
                is_owner,
            )
    token = create_jwt(str(row["id"]), row["username"], row["is_owner"])
    return LoginResponse(token=token, is_owner=row["is_owner"])
