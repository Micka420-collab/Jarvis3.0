"""Skill 'presence' : mode absence + simulation de présence anti-cambriolage.

Quand `away=true`, le service `learning` (via observation table) peut rejouer
des actions IoT typiques de l'utilisateur (éclairage tournant, volets) avec
randomisation pour simuler une présence.
"""

from __future__ import annotations

import datetime as dt
import logging
import os

import asyncpg

from .. import Skill

log = logging.getLogger("skills.presence")


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


async def _set_away(args: dict, ctx: dict) -> dict:
    away = bool(args.get("away", True))
    sim = bool(args.get("simulate_presence", away))
    until = args.get("until_iso")
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE presence_state
                   SET away = $1,
                       simulate_presence = $2,
                       away_until = $3,
                       updated_at = NOW()
                 WHERE id = 1
                """,
                away,
                sim,
                dt.datetime.fromisoformat(until) if until else None,
            )
        return {"away": away, "simulate_presence": sim, "until": until}
    finally:
        await pool.close()


async def _status(args: dict, ctx: dict) -> dict:
    pool = await _pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT away, away_until, simulate_presence, last_seen_owner_at FROM presence_state WHERE id = 1"
            )
        return {
            "away": row["away"],
            "simulate_presence": row["simulate_presence"],
            "away_until": row["away_until"].isoformat() if row["away_until"] else None,
            "last_seen_owner_at": row["last_seen_owner_at"].isoformat()
            if row["last_seen_owner_at"]
            else None,
        }
    finally:
        await pool.close()


def register(s: Skill) -> None:
    s.name = "presence"
    s.description = "Mode absence et simulation de présence"
    s.tool(
        name="presence_set_away",
        description="Active/désactive le mode absence et la simulation de présence anti-cambriolage.",
        input_schema={
            "type": "object",
            "properties": {
                "away": {"type": "boolean"},
                "simulate_presence": {"type": "boolean"},
                "until_iso": {
                    "type": "string",
                    "description": "ISO datetime jusqu'à laquelle le mode est actif",
                },
            },
        },
        handler=_set_away,
        requires_admin=True,
    )
    s.tool(
        name="presence_status",
        description="État courant du mode présence.",
        input_schema={"type": "object", "properties": {}},
        handler=_status,
    )
