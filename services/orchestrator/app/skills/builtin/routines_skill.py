"""Skill 'routines' : créer/lister/exécuter des routines (séquences de tools).

Le service `learning` peut INSERT des routines `learned=true` que l'owner accepte
ou refuse. Une routine peut aussi être créée à la voix : « quand je dis 'mode
soir', tu fais X, Y, Z ».
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import asyncpg

from .. import Skill

log = logging.getLogger("skills.routines")


async def _pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=2,
    )


async def _list(args: dict, ctx: dict) -> dict:
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, trigger, actions, enabled, learned, confidence "
                "FROM routines ORDER BY enabled DESC, learned, name"
            )
        return {
            "routines": [
                {**dict(r), "id": str(r["id"])} for r in rows
            ]
        }
    finally:
        await pool.close()


async def _create(args: dict, ctx: dict) -> dict:
    name = args["name"]
    trigger = args.get("trigger") or {"kind": "voice", "spec": {"phrase": name.lower()}}
    actions = args["actions"]
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO routines(name, trigger, actions, enabled, learned, created_by)
                VALUES($1, $2::jsonb, $3::jsonb, TRUE, FALSE, $4)
                RETURNING id
                """,
                name,
                json.dumps(trigger),
                json.dumps(actions),
                ctx.get("user_id"),
            )
        return {"id": str(row["id"]), "status": "created"}
    finally:
        await pool.close()


async def _enable(args: dict, ctx: dict) -> dict:
    rid = args["id"]
    enabled = args.get("enabled", True)
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE routines SET enabled = $1 WHERE id = $2", enabled, rid
            )
        return {"id": rid, "enabled": enabled}
    finally:
        await pool.close()


async def _run(args: dict, ctx: dict) -> dict:
    """Exécute une routine maintenant (utile pour test)."""
    import httpx

    rid = args["id"]
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT actions FROM routines WHERE id = $1 AND enabled", rid
            )
        if row is None:
            return {"error": "routine inconnue ou désactivée"}
        actions: list[dict[str, Any]] = json.loads(row["actions"]) if isinstance(
            row["actions"], str
        ) else row["actions"]
        results = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for a in actions:
                tool = a.get("tool")
                args_ = a.get("args") or {}
                if tool == "iot_command":
                    r = await client.post("http://iot:8002/command", json=args_)
                    results.append({"tool": tool, "ok": r.status_code == 200})
        async with pool.acquire() as conn:
            await conn.execute("UPDATE routines SET last_run_at = NOW() WHERE id = $1", rid)
        return {"id": rid, "executed": len(results), "results": results}
    finally:
        await pool.close()


def register(s: Skill) -> None:
    s.name = "routines"
    s.description = "Routines (scénarios multi-actions)"
    s.tool(
        name="routines_list",
        description="Liste toutes les routines (manuelles + apprises).",
        input_schema={"type": "object", "properties": {}},
        handler=_list,
    )
    s.tool(
        name="routines_create",
        description="Crée une routine. trigger = {kind: voice|time|event, spec: ...}, actions = [{tool, args}].",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "trigger": {"type": "object"},
                "actions": {"type": "array"},
            },
            "required": ["name", "actions"],
        },
        handler=_create,
        requires_admin=True,
    )
    s.tool(
        name="routines_enable",
        description="Active/désactive une routine.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "enabled": {"type": "boolean"},
            },
            "required": ["id"],
        },
        handler=_enable,
        requires_admin=True,
    )
    s.tool(
        name="routines_run",
        description="Exécute une routine immédiatement (test).",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
        handler=_run,
        requires_admin=True,
    )
