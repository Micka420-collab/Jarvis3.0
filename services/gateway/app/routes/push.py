"""Web Push (notifications PWA).

VAPID config :
    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY (PEM ou base64url)
    VAPID_SUBJECT (mailto:owner@example.com)

Génération des clés une seule fois :
    docker run --rm node:20 npx web-push generate-vapid-keys --json
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import current_user, require_owner
from ..db import get_pool

router = APIRouter()
log = logging.getLogger("gateway.push")


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {p256dh, auth}


@router.get("/public-key")
async def public_key() -> dict:
    return {"key": os.getenv("VAPID_PUBLIC_KEY", "")}


@router.post("/subscribe")
async def subscribe(
    body: PushSubscription, user: Annotated[dict, Depends(current_user)]
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
               SET push_subscriptions = COALESCE(push_subscriptions, '[]'::jsonb)
                 || $1::jsonb
             WHERE id = $2
            """,
            json.dumps([body.model_dump()]),
            user["sub"],
        )
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(
    body: PushSubscription, user: Annotated[dict, Depends(current_user)]
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetchrow(
            "SELECT push_subscriptions FROM users WHERE id = $1", user["sub"]
        )
        subs = rows["push_subscriptions"] if rows and rows["push_subscriptions"] else []
        subs = [s for s in subs if s.get("endpoint") != body.endpoint]
        await conn.execute(
            "UPDATE users SET push_subscriptions = $1::jsonb WHERE id = $2",
            json.dumps(subs),
            user["sub"],
        )
    return {"ok": True}


class PushSendRequest(BaseModel):
    title: str
    body: str
    url: str | None = None
    only_owner: bool = False


@router.post("/send")
async def send(req: PushSendRequest, user: Annotated[dict, Depends(require_owner)]) -> dict:
    """Envoie une notif à toutes les subscriptions actives.

    Sur les setups petits (familial), pas besoin de queue : push direct synchrone.
    Pour grosse échelle, déporter vers un worker background.
    """
    try:
        from pywebpush import WebPushException, webpush  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="pywebpush non installé — ajoute pywebpush au gateway/requirements.txt",
        )
    private_key = os.getenv("VAPID_PRIVATE_KEY", "")
    subject = os.getenv("VAPID_SUBJECT", "mailto:owner@example.com")
    if not private_key:
        raise HTTPException(status_code=500, detail="VAPID_PRIVATE_KEY manquant")

    pool = await get_pool()
    async with pool.acquire() as conn:
        if req.only_owner:
            rows = await conn.fetch(
                "SELECT push_subscriptions FROM users WHERE is_owner = TRUE"
            )
        else:
            rows = await conn.fetch("SELECT push_subscriptions FROM users")

    payload = json.dumps({"title": req.title, "body": req.body, "url": req.url or "/"})
    sent = 0
    failed = 0
    for r in rows:
        for sub in r["push_subscriptions"] or []:
            try:
                webpush(
                    subscription_info=sub,
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": subject},
                )
                sent += 1
            except WebPushException as e:
                log.warning("push failed: %s", e)
                failed += 1
    return {"sent": sent, "failed": failed}
