"""JWT + gating voix-print pour les commandes admin."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer = HTTPBearer(auto_error=False)


def create_jwt(user_id: str, username: str, is_owner: bool) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "is_owner": is_owner,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return decode_jwt(creds.credentials)


# ---------------------------------------------------------------------------
# Cooldown commandes admin (anti-replay basique)
# ---------------------------------------------------------------------------

_LAST_ADMIN_AT: dict[str, float] = {}


def check_admin_cooldown(user_id: str) -> None:
    now = time.monotonic()
    last = _LAST_ADMIN_AT.get(user_id, 0.0)
    if now - last < settings.admin_command_cooldown_seconds:
        wait = int(settings.admin_command_cooldown_seconds - (now - last))
        raise HTTPException(
            status_code=429,
            detail=f"admin command cooldown, attendre {wait}s",
        )
    _LAST_ADMIN_AT[user_id] = now


# ---------------------------------------------------------------------------
# Décorateur owner-only (à utiliser sur les routes sensibles)
# ---------------------------------------------------------------------------


async def require_owner(user: Annotated[dict, Depends(current_user)]) -> dict:
    if not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="owner only")
    check_admin_cooldown(user["sub"])
    return user


def require_owner_voice(verified: dict | None) -> bool:
    """Helper utilisé côté orchestrator pour gater par voix-print.

    `verified` est l'event VoiceIdentityVerified (dict).
    """
    if verified is None:
        return False
    if not verified.get("is_owner"):
        return False
    similarity = verified.get("similarity", 0.0)
    if similarity >= settings.voiceprint_threshold_accept:
        return True
    if similarity >= settings.voiceprint_threshold_grey:
        return bool(verified.get("challenge_passed"))
    return False
