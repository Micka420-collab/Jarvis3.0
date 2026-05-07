"""Service mémoire — version améliorée.

Fonctionnalités :
- /remember          : ingest avec chunking + classification auto + dedup
- /recall            : hybrid search (vectoriel + BM25) + scoring composite
                       (similarity + récence + importance + utilisation)
- /facts             : CRUD complet + listing avec filtres
- /facts/{id}        : GET, PATCH, DELETE
- /feedback          : booste l'importance d'un fact rappelé utile
- /stats             : compteurs par kind / user / most-recalled
- /forget            : supprime les vieux faits non rappelés et peu importants
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import facts as facts_db
from .chunker import chunk_text
from .classifier import auto_importance, classify
from .embedder import Embedder
from .qdrant_client import MemoryStore
from .scoring import (
    ScoringWeights,
    composite_score,
    reciprocal_rank_fusion,
)

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
    log.info("memory ready (embed_dim=%d, collection=%s)", embedder.dim, store.collection)
    yield
    await pool.close()


app = FastAPI(title="Jarvis Memory", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RememberRequest(BaseModel):
    text: str
    user_id: str | None = None
    tags: list[str] = []
    kind: str | None = None              # auto-classified si None
    importance: float | None = None       # auto si None
    source: str | None = None             # ex: "orchestrator", "user", "learning"
    deduplicate: bool = True              # skip si déjà mémorisé


class RememberResponse(BaseModel):
    fact_id: str
    chunks: int
    kind: str
    importance: float
    duplicate_of: str | None = None


class UpdateFactBody(BaseModel):
    text: str | None = None
    tags: list[str] | None = None
    importance: float | None = None
    kind: str | None = None


class FeedbackBody(BaseModel):
    fact_id: str
    helpful: bool = True
    delta: float = Field(0.05, ge=0.0, le=0.5)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "memory", "version": app.version}


@app.post("/remember", response_model=RememberResponse)
async def remember(req: RememberRequest) -> RememberResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text vide")

    # 1. Déduplication
    if req.deduplicate:
        dup = await facts_db.find_duplicate(app.state.pool, user_id=req.user_id, text=text)
        if dup is not None:
            log.info("dedup: skip insert, similar to %s", dup)
            existing = await facts_db.get_fact(app.state.pool, dup) or {}
            return RememberResponse(
                fact_id=dup,
                chunks=0,
                kind=existing.get("kind", "fact"),
                importance=existing.get("importance", 0.5),
                duplicate_of=dup,
            )

    # 2. Classification + importance auto
    kind = req.kind or classify(text)
    importance = req.importance if req.importance is not None else auto_importance(text, kind)

    # 3. Insert fact (texte canonique, indexé full-text)
    fact_id = await facts_db.insert_fact(
        app.state.pool,
        user_id=req.user_id,
        text=text,
        tags=req.tags,
        kind=kind,
        importance=importance,
        source=req.source,
    )

    # 4. Chunking + embedding + upsert Qdrant
    chunks = chunk_text(text)
    vectors = app.state.embedder.encode(chunks, use_cache=False)
    payloads = [
        {
            "fact_id": fact_id,
            "user_id": req.user_id,
            "kind": kind,
            "tags": req.tags,
            "importance": importance,
            "text": chunk,
            "chunk_idx": i,
            "n_chunks": len(chunks),
        }
        for i, chunk in enumerate(chunks)
    ]
    await app.state.store.upsert(vectors, payloads)

    return RememberResponse(
        fact_id=fact_id, chunks=len(chunks), kind=kind, importance=importance,
        duplicate_of=None,
    )


@app.get("/recall")
async def recall(
    query: str = Query(...),
    k: int = 5,
    user_id: str = "",
    kind: str = "",
    hybrid: bool = True,
    min_score: float = 0.0,
) -> dict:
    """Search hybride : vectoriel (Qdrant) + BM25 (Postgres) fusionnés via RRF,
    puis re-scoring composite (similarity + récence + importance + use).
    """
    if not query.strip():
        return {"results": [], "query": query}

    user = user_id or None
    kfilter = kind or None
    pool = app.state.pool

    # 1. Recherche vectorielle élargie pour avoir plus de candidats
    vec = app.state.embedder.encode([query])[0]
    vector_hits = await app.state.store.search(
        vec, k=max(k * 4, 16), user_filter=user, kind_filter=kfilter,
    )
    # Dédoublonne par fact_id (chunks multiples → on garde le meilleur score)
    seen_facts: dict[str, dict] = {}
    for h in vector_hits:
        fid = h.get("fact_id")
        if not fid:
            continue
        if fid not in seen_facts or h["score"] > seen_facts[fid]["score"]:
            seen_facts[fid] = h

    # 2. BM25 (si hybrid)
    bm25_facts: dict[str, dict] = {}
    if hybrid:
        bm25_results = await facts_db.bm25_search(
            pool, query=query, user_id=user, kind=kfilter, limit=k * 4,
        )
        for r in bm25_results:
            bm25_facts[r["id"]] = r

    # 3. Reciprocal Rank Fusion
    rankings = [list(seen_facts.keys())]
    if bm25_facts:
        rankings.append(list(bm25_facts.keys()))
    fused = reciprocal_rank_fusion([r for r in rankings if r])

    # 4. Récupération + re-scoring composite
    weights = ScoringWeights()
    out: list[dict] = []
    for fact_id, _rrf in fused[: k * 3]:
        meta = seen_facts.get(fact_id) or bm25_facts.get(fact_id) or {}
        full = await facts_db.get_fact(pool, fact_id)
        if not full:
            continue
        similarity = float(meta.get("score", meta.get("bm25_score", 0.0)))
        created_at = full.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = dt.datetime.fromisoformat(created_at)
            except ValueError:
                created_at = dt.datetime.now(dt.timezone.utc)
        elif not isinstance(created_at, dt.datetime):
            created_at = dt.datetime.now(dt.timezone.utc)
        score = composite_score(
            similarity=similarity,
            created_at=created_at,
            importance=float(full.get("importance", 0.5)),
            recall_count=int(full.get("recall_count", 0)),
            weights=weights,
        )
        if score < min_score:
            continue
        out.append({**full, "score": round(score, 4), "similarity": round(similarity, 4)})

    out.sort(key=lambda r: -r["score"])
    out = out[:k]

    # 5. Track recall
    if out:
        await facts_db.record_recall(pool, [r["id"] for r in out])

    return {"results": out, "query": query}


# --- CRUD facts ---


@app.get("/facts")
async def list_facts(
    user_id: str = "", kind: str = "", tag: str = "",
    limit: int = 100, offset: int = 0,
) -> dict:
    rows = await facts_db.list_facts(
        app.state.pool,
        user_id=user_id or None, kind=kind or None, tag=tag or None,
        limit=limit, offset=offset,
    )
    return {"results": rows, "limit": limit, "offset": offset}


@app.get("/facts/{fact_id}")
async def get_fact(fact_id: str) -> dict:
    row = await facts_db.get_fact(app.state.pool, fact_id)
    if not row:
        raise HTTPException(status_code=404, detail="fact inconnu")
    return row


@app.patch("/facts/{fact_id}")
async def update_fact(fact_id: str, body: UpdateFactBody) -> dict:
    found = await facts_db.update_fact(
        app.state.pool, fact_id,
        text=body.text, tags=body.tags,
        importance=body.importance, kind=body.kind,
    )
    if not found:
        raise HTTPException(status_code=404, detail="fact inconnu")
    # Si le texte change, ré-embed et re-upsert les chunks
    if body.text:
        await app.state.store.delete_by_fact_id(fact_id)
        chunks = chunk_text(body.text)
        vectors = app.state.embedder.encode(chunks, use_cache=False)
        full = await facts_db.get_fact(app.state.pool, fact_id) or {}
        payloads = [
            {
                "fact_id": fact_id,
                "user_id": full.get("user_id"),
                "kind": full.get("kind", "fact"),
                "tags": full.get("tags", []),
                "importance": full.get("importance", 0.5),
                "text": c,
                "chunk_idx": i,
                "n_chunks": len(chunks),
            }
            for i, c in enumerate(chunks)
        ]
        await app.state.store.upsert(vectors, payloads)
    return await facts_db.get_fact(app.state.pool, fact_id) or {}


@app.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str) -> dict:
    ok = await facts_db.delete_fact(app.state.pool, fact_id)
    if not ok:
        raise HTTPException(status_code=404, detail="fact inconnu")
    await app.state.store.delete_by_fact_id(fact_id)
    return {"deleted": True, "fact_id": fact_id}


# --- Feedback / forget / stats ---


@app.post("/feedback")
async def feedback(body: FeedbackBody) -> dict:
    """L'orchestrator/admin signale qu'un recall a été utile (boost) ou pas (down).
    Borne l'importance dans [0,1].
    """
    fact = await facts_db.get_fact(app.state.pool, body.fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="fact inconnu")
    delta = body.delta if body.helpful else -body.delta
    new_imp = max(0.0, min(1.0, float(fact.get("importance", 0.5)) + delta))
    await facts_db.update_fact(app.state.pool, body.fact_id, importance=new_imp)
    if body.helpful:
        await facts_db.record_recall(app.state.pool, [body.fact_id])
    return {"fact_id": body.fact_id, "new_importance": new_imp}


@app.post("/forget")
async def forget(max_age_days: int = 365, importance_max: float = 0.4) -> dict:
    """Cleanup des vieux faits non rappelés et peu importants."""
    n = await facts_db.forget_old(
        app.state.pool, max_age_days=max_age_days, importance_max=importance_max,
    )
    return {"forgotten": n, "max_age_days": max_age_days, "importance_max": importance_max}


@app.get("/stats")
async def get_stats() -> dict:
    s = await facts_db.stats(app.state.pool)
    try:
        s["qdrant_points"] = await app.state.store.count()
    except Exception:
        s["qdrant_points"] = None
    s["embed_cache_size"] = len(app.state.embedder.cache)
    return s
