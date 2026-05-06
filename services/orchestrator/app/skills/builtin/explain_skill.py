"""Skill 'explain' : Jarvis explique son raisonnement précédent.

Lit la dernière trace `reasoning_traces` pour la session courante.
"""

from __future__ import annotations

import logging
import os

import asyncpg

from .. import Skill

log = logging.getLogger("skills.explain")


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


async def _last(args: dict, ctx: dict) -> dict:
    session_id = ctx.get("session_id") or args.get("session_id")
    if not session_id:
        return {"error": "pas de session"}
    pool = await _pool()
    try:
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
            return {"explanation": "Je n'ai pas de trace pour cette session."}
        return {
            "user_text": row["user_text"],
            "intent": row["intent"],
            "tools": row["tools_called"],
            "memory_hits": row["memory_hits"],
            "response": row["response"],
            "duration_ms": row["duration_ms"],
            "ts": row["ts"].isoformat(),
        }
    finally:
        await pool.close()


def register(s: Skill) -> None:
    s.name = "explain"
    s.description = "Explainability : ce que Jarvis a fait au tour précédent"
    s.tool(
        name="explain_last_action",
        description="Renvoie la trace du dernier raisonnement de Jarvis pour cette session.",
        input_schema={"type": "object", "properties": {}},
        handler=_last,
    )
