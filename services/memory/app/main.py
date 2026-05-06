"""Service mémoire : remember + recall."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel

from .embedder import Embedder
from .facts import insert_fact
from .qdrant_client import MemoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("memory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = Embedder()
    store = MemoryStore(dim=embedder.dim)
    await store.ensure_collection()
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=5,
    )
    app.state.embedder = embedder
    app.state.store = store
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(title="Jarvis Memory", version="0.1.0", lifespan=lifespan)


class RememberRequest(BaseModel):
    text: str
    user_id: str | None = None
    tags: list[str] = []


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "memory"}


@app.post("/remember")
async def remember(req: RememberRequest) -> dict:
    fact_id = await insert_fact(app.state.pool, req.user_id, req.text, req.tags)
    vec = app.state.embedder.encode([req.text])[0]
    await app.state.store.upsert(
        [vec],
        [{"fact_id": fact_id, "text": req.text, "user_id": req.user_id, "tags": req.tags}],
    )
    return {"fact_id": fact_id, "stored": True}


@app.get("/recall")
async def recall(query: str = Query(...), k: int = 5, user_id: str = "") -> dict:
    vec = app.state.embedder.encode([query])[0]
    hits = await app.state.store.search(vec, k=k, user_filter=user_id or None)
    return {"results": hits}
