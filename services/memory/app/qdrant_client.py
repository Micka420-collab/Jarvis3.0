"""Wrapper Qdrant pour la collection `conversations`.

Améliorations vs version initiale :
- delete par fact_id (cohérence Postgres ↔ Qdrant)
- search renvoie aussi le `id` Qdrant (utile pour record_recall)
- payload schema indexé : user_id, fact_id, kind (filtres rapides)
"""

from __future__ import annotations

import logging
import os
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

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
            await self._ensure_indexes()
            return
        log.info("creating qdrant collection %s (dim=%d)", self.collection, self.dim)
        await self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
        )
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        for field, schema in [
            ("user_id", PayloadSchemaType.KEYWORD),
            ("fact_id", PayloadSchemaType.KEYWORD),
            ("kind", PayloadSchemaType.KEYWORD),
        ]:
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception:
                pass  # déjà créé

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
        self,
        vector: list[float],
        *,
        k: int = 5,
        user_filter: str | None = None,
        kind_filter: str | None = None,
    ) -> list[dict]:
        conditions: list[FieldCondition] = []
        if user_filter:
            conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_filter)))
        if kind_filter:
            conditions.append(FieldCondition(key="kind", match=MatchValue(value=kind_filter)))
        flt = Filter(must=conditions) if conditions else None
        results = await self.client.search(
            collection_name=self.collection, query_vector=vector, limit=k, query_filter=flt
        )
        return [
            {"id": str(r.id), "score": float(r.score), **(r.payload or {})}
            for r in results
        ]

    async def delete_by_fact_id(self, fact_id: str) -> int:
        """Supprime tous les points Qdrant correspondant à un fact (chunks)."""
        flt = Filter(must=[FieldCondition(key="fact_id", match=MatchValue(value=fact_id))])
        result = await self.client.delete(
            collection_name=self.collection,
            points_selector=flt,
        )
        return getattr(result, "operation_id", 0) or 0

    async def count(self) -> int:
        info = await self.client.count(self.collection)
        return getattr(info, "count", 0)
