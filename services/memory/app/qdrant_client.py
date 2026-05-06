"""Wrapper Qdrant pour la collection `conversations`."""

from __future__ import annotations

import logging
import os
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

log = logging.getLogger("memory.qdrant")


class MemoryStore:
    def __init__(self, dim: int) -> None:
        self.host = os.getenv("QDRANT_HOST", "qdrant")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.collection = os.getenv("QDRANT_COLLECTION", "conversations")
        self.dim = dim
        self.client = AsyncQdrantClient(host=self.host, port=self.port)

    async def ensure_collection(self) -> None:
        existing = await self.client.get_collections()
        if self.collection in [c.name for c in existing.collections]:
            return
        log.info("creating qdrant collection %s (dim=%d)", self.collection, self.dim)
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
        )

    async def upsert(
        self, vectors: list[list[float]], payloads: list[dict]
    ) -> list[str]:
        ids = [str(uuid.uuid4()) for _ in vectors]
        points = [
            PointStruct(id=i, vector=v, payload=p) for i, v, p in zip(ids, vectors, payloads)
        ]
        await self.client.upsert(self.collection, points=points)
        return ids

    async def search(
        self, vector: list[float], k: int = 5, user_filter: str | None = None
    ) -> list[dict]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        flt = None
        if user_filter:
            flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_filter))])
        results = await self.client.search(
            collection_name=self.collection, query_vector=vector, limit=k, query_filter=flt
        )
        return [
            {"id": str(r.id), "score": r.score, **(r.payload or {})} for r in results
        ]
