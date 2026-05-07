"""CRUD pour les faits long-terme + hybrid search BM25 + stats."""

from __future__ import annotations

import datetime as dt
from typing import Any

import asyncpg


async def insert_fact(
    pool: asyncpg.Pool,
    *,
    user_id: str | None,
    text: str,
    tags: list[str],
    kind: str = "fact",
    importance: float = 0.5,
    source: str | None = None,
) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO facts(user_id, text, tags, kind, importance, source)
            VALUES($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id, text, tags, kind, importance, source,
        )
    return str(row["id"])


async def update_fact(
    pool: asyncpg.Pool,
    fact_id: str,
    *,
    text: str | None = None,
    tags: list[str] | None = None,
    importance: float | None = None,
    kind: str | None = None,
) -> bool:
    """Update sélectif. Retourne True si la ligne existait."""
    sets: list[str] = []
    values: list[Any] = []
    if text is not None:
        sets.append(f"text = ${len(values) + 1}"); values.append(text)
    if tags is not None:
        sets.append(f"tags = ${len(values) + 1}"); values.append(tags)
    if importance is not None:
        sets.append(f"importance = ${len(values) + 1}"); values.append(importance)
    if kind is not None:
        sets.append(f"kind = ${len(values) + 1}"); values.append(kind)
    if not sets:
        return True
    values.append(fact_id)
    async with pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE facts SET {', '.join(sets)} WHERE id = ${len(values)}",
            *values,
        )
    return result.endswith(" 1")


async def delete_fact(pool: asyncpg.Pool, fact_id: str) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM facts WHERE id = $1", fact_id)
    return result.endswith(" 1")


async def get_fact(pool: asyncpg.Pool, fact_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM facts WHERE id = $1", fact_id)
    return _row_to_dict(row) if row else None


async def record_recall(pool: asyncpg.Pool, fact_ids: list[str]) -> None:
    """Incrémente recall_count + maj last_recalled_at pour les ids donnés."""
    if not fact_ids:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE facts
               SET recall_count = recall_count + 1,
                   last_recalled_at = NOW()
             WHERE id = ANY($1::uuid[])
            """,
            fact_ids,
        )


async def find_duplicate(
    pool: asyncpg.Pool, *, user_id: str | None, text: str, similarity_min: float = 0.92
) -> str | None:
    """Cherche un fait existant quasi-identique (similarity trigramme).

    Utilise pg_trgm si dispo, sinon fallback simple sur égalité exacte.
    """
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                SELECT id, similarity(text, $1) AS sim FROM facts
                 WHERE ($2::uuid IS NULL OR user_id = $2)
                   AND similarity(text, $1) >= $3
              ORDER BY sim DESC
                 LIMIT 1
                """,
                text, user_id, similarity_min,
            )
        except Exception:
            row = await conn.fetchrow(
                "SELECT id FROM facts WHERE text = $1 AND ($2::uuid IS NULL OR user_id = $2) LIMIT 1",
                text, user_id,
            )
    return str(row["id"]) if row else None


async def bm25_search(
    pool: asyncpg.Pool, *, query: str, user_id: str | None = None,
    kind: str | None = None, limit: int = 20,
) -> list[dict]:
    """Recherche full-text BM25 via tsvector. Retourne id + score normalisé."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text, tags, kind, importance, recall_count, created_at,
                   ts_rank_cd(tsv, plainto_tsquery('french', $1)) AS rank
              FROM facts
             WHERE tsv @@ plainto_tsquery('french', $1)
               AND ($2::uuid IS NULL OR user_id = $2)
               AND ($3::text IS NULL OR kind = $3)
          ORDER BY rank DESC
             LIMIT $4
            """,
            query, user_id, kind, limit,
        )
    out = []
    max_rank = max((r["rank"] for r in rows), default=1.0) or 1.0
    for r in rows:
        d = _row_to_dict(r)
        d["bm25_score"] = float(r["rank"]) / max_rank
        out.append(d)
    return out


async def list_facts(
    pool: asyncpg.Pool,
    *,
    user_id: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM facts
             WHERE ($1::uuid IS NULL OR user_id = $1)
               AND ($2::text IS NULL OR kind = $2)
               AND ($3::text IS NULL OR $3 = ANY(tags))
          ORDER BY created_at DESC
             LIMIT $4 OFFSET $5
            """,
            user_id, kind, tag, limit, offset,
        )
    return [_row_to_dict(r) for r in rows]


async def stats(pool: asyncpg.Pool) -> dict:
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM facts")
        by_kind = await conn.fetch("SELECT kind, COUNT(*) AS n FROM facts GROUP BY kind ORDER BY n DESC")
        by_user = await conn.fetch(
            "SELECT user_id, COUNT(*) AS n FROM facts GROUP BY user_id ORDER BY n DESC LIMIT 20"
        )
        avg_importance = await conn.fetchval("SELECT AVG(importance)::float FROM facts")
        most_recalled = await conn.fetch(
            """
            SELECT id, text, kind, recall_count, last_recalled_at FROM facts
             WHERE recall_count > 0
          ORDER BY recall_count DESC
             LIMIT 10
            """
        )
    return {
        "total": total or 0,
        "by_kind": [{"kind": r["kind"], "n": r["n"]} for r in by_kind],
        "by_user": [{"user_id": str(r["user_id"]) if r["user_id"] else None, "n": r["n"]} for r in by_user],
        "avg_importance": avg_importance,
        "most_recalled": [
            {
                "id": str(r["id"]),
                "text": r["text"][:120],
                "kind": r["kind"],
                "recall_count": r["recall_count"],
                "last_recalled_at": r["last_recalled_at"].isoformat() if r["last_recalled_at"] else None,
            }
            for r in most_recalled
        ],
    }


async def forget_old(
    pool: asyncpg.Pool, *, max_age_days: int = 365, importance_max: float = 0.4
) -> int:
    """Supprime les faits plus vieux que `max_age_days` ET d'importance basse
    ET jamais rappelés. Garde les souvenirs précieux indéfiniment.
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM facts
             WHERE created_at < NOW() - ($1 || ' days')::interval
               AND importance <= $2
               AND recall_count = 0
            """,
            str(max_age_days), importance_max,
        )
    try:
        return int(result.rsplit(" ", 1)[-1])
    except Exception:
        return 0


def _row_to_dict(row: asyncpg.Record | None) -> dict:
    if row is None:
        return {}
    d = dict(row)
    d["id"] = str(d["id"])
    if d.get("user_id"):
        d["user_id"] = str(d["user_id"])
    for ts_field in ("created_at", "updated_at", "last_recalled_at"):
        if d.get(ts_field) and isinstance(d[ts_field], dt.datetime):
            d[ts_field] = d[ts_field].isoformat()
    d.pop("tsv", None)  # ne pas exposer le tsvector binaire
    return d
