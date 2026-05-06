"""Endpoints admin agrégés (dashboard + proxy vers les services internes).

Toutes les routes ici sont gated owner via require_owner.
"""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_owner
from ..db import get_pool

router = APIRouter()


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def dashboard(user: Annotated[dict, Depends(require_owner)]) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        devices_count = await conn.fetchval("SELECT COUNT(*) FROM devices")
        routines_count = await conn.fetchval("SELECT COUNT(*) FROM routines")
        learned_pending = await conn.fetchval(
            "SELECT COUNT(*) FROM routines WHERE learned = TRUE AND enabled = FALSE"
        )
        recent_alerts = await conn.fetchval(
            "SELECT COUNT(*) FROM auth_events WHERE ts > NOW() - INTERVAL '24 hours'"
        )
        recent_traces = await conn.fetchval(
            "SELECT COUNT(*) FROM reasoning_traces WHERE ts > NOW() - INTERVAL '24 hours'"
        )
        try:
            agent_tasks_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_tasks WHERE created_at > NOW() - INTERVAL '24 hours'"
            )
        except Exception:
            agent_tasks_24h = 0

    services_status: dict[str, bool] = {}
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in [
            ("llm", "http://llm:8000/health"),
            ("orchestrator", "http://orchestrator:8001/health"),
            ("memory", "http://memory:8004/health"),
            ("iot", "http://iot:8002/health"),
            ("security", "http://security:8003/health"),
            ("agents", "http://agents:8005/health"),
        ]:
            try:
                r = await client.get(url)
                services_status[name] = r.status_code == 200
            except Exception:
                services_status[name] = False

    return {
        "counts": {
            "users": users_count,
            "devices": devices_count,
            "routines": routines_count,
            "learned_pending": learned_pending,
        },
        "activity_24h": {
            "auth_events": recent_alerts,
            "reasoning_traces": recent_traces,
            "agent_tasks": agent_tasks_24h,
        },
        "services": services_status,
    }


# ---------------------------------------------------------------------------
# Proxies (orchestrator skills, agents, security, iot)
# ---------------------------------------------------------------------------


async def _proxy_get(url: str, params: dict | None = None) -> dict | list:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params or {})
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _proxy_post(url: str, body: dict | None = None) -> dict | list:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=body or {})
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


# --- Skills ---


@router.get("/skills")
async def list_skills(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_get("http://orchestrator:8001/skills")


@router.post("/skills/reload")
async def reload_skills(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_post("http://orchestrator:8001/skills/reload")


# --- Agents ---


@router.get("/agents")
async def list_agents(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_get("http://agents:8005/agents")


@router.get("/agent-tasks")
async def list_agent_tasks(
    user: Annotated[dict, Depends(require_owner)], limit: int = 50
):
    return await _proxy_get("http://agents:8005/tasks", params={"limit": limit})


class DelegateBody(BaseModel):
    agent: str
    goal: str


@router.post("/agent-delegate")
async def delegate_agent(
    body: DelegateBody, user: Annotated[dict, Depends(require_owner)]
):
    return await _proxy_post(
        "http://agents:8005/delegate",
        {"agent": body.agent, "goal": body.goal, "user_id": user["sub"], "context": {}},
    )


# --- IoT ---


@router.get("/devices")
async def list_devices(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_get("http://iot:8002/devices")


@router.post("/devices/discover/ha")
async def discover_ha(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_post("http://iot:8002/discover/ha")


@router.post("/devices/discover/zigbee")
async def discover_zigbee(user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_post("http://iot:8002/discover/zigbee")


# --- Routines ---


@router.get("/routines")
async def list_routines(user: Annotated[dict, Depends(require_owner)]):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, trigger, actions, enabled, learned, confidence,
                   created_at, last_run_at
              FROM routines
          ORDER BY enabled DESC, learned, name
            """
        )
    return [
        {
            **dict(r),
            "id": str(r["id"]),
            "created_at": r["created_at"].isoformat(),
            "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
        }
        for r in rows
    ]


class RoutineToggleBody(BaseModel):
    enabled: bool


class RoutineCreateBody(BaseModel):
    name: str
    trigger: dict
    actions: list[dict]
    enabled: bool = True


@router.post("/routines")
async def create_routine(
    body: RoutineCreateBody, user: Annotated[dict, Depends(require_owner)]
) -> dict:
    import json as _json
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO routines(name, trigger, actions, enabled, learned, confidence)
            VALUES($1, $2::jsonb, $3::jsonb, $4, FALSE, 1.0)
            RETURNING id
            """,
            body.name,
            _json.dumps(body.trigger),
            _json.dumps(body.actions),
            body.enabled,
        )
    return {"id": str(row["id"]), "created": True}


@router.patch("/routines/{routine_id}")
async def toggle_routine(
    routine_id: str,
    body: RoutineToggleBody,
    user: Annotated[dict, Depends(require_owner)],
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE routines SET enabled = $1 WHERE id = $2", body.enabled, routine_id
        )
    return {"id": routine_id, "enabled": body.enabled}


@router.delete("/routines/{routine_id}")
async def delete_routine(
    routine_id: str, user: Annotated[dict, Depends(require_owner)]
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM routines WHERE id = $1", routine_id)
    return {"deleted": True}


# --- Traces ---


@router.get("/traces")
async def list_traces(
    user: Annotated[dict, Depends(require_owner)], limit: int = 50
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, ts, session_id, user_id, user_text, intent,
                   tools_called, response, duration_ms
              FROM reasoning_traces
          ORDER BY ts DESC
             LIMIT $1
            """,
            limit,
        )
    return [
        {
            **dict(r),
            "id": int(r["id"]),
            "ts": r["ts"].isoformat(),
            "user_id": str(r["user_id"]) if r["user_id"] else None,
        }
        for r in rows
    ]


# --- Push notifications test ---


class PushTestBody(BaseModel):
    title: str = "Jarvis"
    body: str = "Test depuis l'admin console."


@router.post("/push-test")
async def push_test(body: PushTestBody, user: Annotated[dict, Depends(require_owner)]):
    return await _proxy_post(
        "http://gateway:8000/api/push/send",
        {"title": body.title, "body": body.body, "only_owner": True},
    )


# --- Wizard / connexions ---


class TestConnBody(BaseModel):
    kind: str   # "homeassistant" | "argus" | "frigate" | "anthropic" | "ollama" | "mqtt"
    url: str | None = None
    token: str | None = None
    api_key: str | None = None
    extra: dict = {}


@router.post("/wizard/test")
async def wizard_test(body: TestConnBody, user: Annotated[dict, Depends(require_owner)]) -> dict:
    """Teste une connexion sans persister les valeurs. Réponse uniforme :
    {"ok": bool, "detail": str, "latency_ms": int}.
    """
    import time

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=4.0) as c:
            if body.kind == "homeassistant":
                r = await c.get(
                    f"{body.url}/api/",
                    headers={"Authorization": f"Bearer {body.token}"},
                )
                ok = r.status_code == 200
                detail = r.json().get("message", "") if ok else r.text[:200]
            elif body.kind == "argus":
                r = await c.get(
                    f"{body.url}/api/health",
                    headers={"Authorization": f"Bearer {body.token}"} if body.token else {},
                )
                ok, detail = r.status_code == 200, r.text[:200]
            elif body.kind == "frigate":
                r = await c.get(f"{body.url}/api/version")
                ok, detail = r.status_code == 200, r.text[:200]
            elif body.kind == "anthropic":
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": body.api_key or "",
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": body.extra.get("model", "claude-haiku-4-5-20251001"),
                        "max_tokens": 8,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
                ok = r.status_code == 200
                detail = r.text[:200]
            elif body.kind == "openrouter":
                r = await c.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {body.api_key or ''}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://jarvis.local",
                        "X-Title": "Jarvis 3.0",
                    },
                    json={
                        "model": body.extra.get("model", "anthropic/claude-sonnet-4-6"),
                        "max_tokens": 8,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                )
                ok = r.status_code == 200
                detail = r.text[:200]
            elif body.kind == "ollama":
                r = await c.get(f"{body.url or 'http://ollama:11434'}/api/tags")
                ok, detail = r.status_code == 200, r.text[:200]
            elif body.kind == "mqtt":
                # test via service iot
                r = await c.get("http://iot:8002/health")
                ok, detail = r.status_code == 200, r.text[:200]
            else:
                ok, detail = False, f"kind inconnu: {body.kind}"
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    return {
        "ok": ok,
        "detail": detail,
        "latency_ms": int((time.time() - t0) * 1000),
    }


@router.get("/wizard/state")
async def wizard_state(user: Annotated[dict, Depends(require_owner)]) -> dict:
    """État de chaque connexion (sans révéler les secrets)."""
    pool = await get_pool()
    services_health = {}
    async with httpx.AsyncClient(timeout=2.0) as c:
        for name, url in [
            ("orchestrator", "http://orchestrator:8001/health"),
            ("memory", "http://memory:8004/health"),
            ("iot", "http://iot:8002/health"),
            ("security", "http://security:8003/health"),
            ("agents", "http://agents:8005/health"),
        ]:
            try:
                r = await c.get(url)
                services_health[name] = r.status_code == 200
            except Exception:
                services_health[name] = False
    async with pool.acquire() as conn:
        users_voice = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE voice_enrolled = TRUE"
        )
        users_face = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE face_enrolled = TRUE"
        )
    import os

    return {
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "ollama"),
            "model": os.getenv("LLM_MODEL", ""),
            "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
        "homeassistant": {
            "url": os.getenv("HA_BASE_URL", ""),
            "token_present": bool(os.getenv("HA_LONG_LIVED_TOKEN")),
        },
        "argus": {
            "url": os.getenv("ARGUS_BASE_URL", ""),
            "token_present": bool(os.getenv("ARGUS_API_TOKEN")),
        },
        "frigate": {"url": os.getenv("FRIGATE_API_URL", "")},
        "vapid": {"configured": bool(os.getenv("VAPID_PUBLIC_KEY"))},
        "agents": {
            "hermes": bool(os.getenv("INSTALL_HERMES") == "true"),
            "openclaw": bool(os.getenv("INSTALL_OPENCLAW") == "true"),
        },
        "voice_enrolled_users": users_voice,
        "face_enrolled_users": users_face,
        "services": services_health,
    }


# --- Presence ---


@router.get("/presence")
async def get_presence(user: Annotated[dict, Depends(require_owner)]):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT away, simulate_presence, away_until, last_seen_owner_at FROM presence_state WHERE id = 1"
        )
    if row is None:
        return {"away": False, "simulate_presence": False}
    return {
        "away": row["away"],
        "simulate_presence": row["simulate_presence"],
        "away_until": row["away_until"].isoformat() if row["away_until"] else None,
        "last_seen_owner_at": row["last_seen_owner_at"].isoformat()
        if row["last_seen_owner_at"]
        else None,
    }


class PresenceBody(BaseModel):
    away: bool
    simulate_presence: bool = True
    until_iso: str | None = None


@router.post("/presence")
async def set_presence(
    body: PresenceBody, user: Annotated[dict, Depends(require_owner)]
):
    import datetime as dt

    pool = await get_pool()
    until = dt.datetime.fromisoformat(body.until_iso) if body.until_iso else None
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE presence_state
               SET away = $1, simulate_presence = $2, away_until = $3, updated_at = NOW()
             WHERE id = 1
            """,
            body.away,
            body.simulate_presence,
            until,
        )
    return {"away": body.away, "simulate_presence": body.simulate_presence}
