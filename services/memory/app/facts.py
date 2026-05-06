"""Faits structurés long-terme stockés en Postgres + indexés Qdrant."""

from __future__ import annotations

import asyncpg


async def insert_fact(
    pool: asyncpg.Pool, user_id: str | None, text: str, tags: list[str]
) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO facts(user_id, text, tags) VALUES($1, $2, $3) RETURNING id",
            user_id,
            text,
            tags,
        )
    return str(row["id"])
