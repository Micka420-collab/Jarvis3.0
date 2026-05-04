"""Client Redis Streams unifié pour publier/consommer les événements."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class EventBus:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = redis.Redis(
                host=self.host, port=self.port, decode_responses=True
            )
            await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def publish(self, stream: str, event: BaseModel, maxlen: int = 10_000) -> str:
        await self.connect()
        assert self._client is not None
        payload = {"data": event.model_dump_json()}
        msg_id = await self._client.xadd(stream, payload, maxlen=maxlen, approximate=True)
        return msg_id

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        model: type[T],
        block_ms: int = 5_000,
        count: int = 16,
    ) -> AsyncIterator[tuple[str, T]]:
        """Consomme via Consumer Group (load-balancing + ack)."""
        await self.connect()
        assert self._client is not None
        try:
            await self._client.xgroup_create(stream, group, id="$", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        while True:
            try:
                msgs = await self._client.xreadgroup(
                    group, consumer, {stream: ">"}, count=count, block=block_ms
                )
            except asyncio.CancelledError:
                raise
            if not msgs:
                continue
            for _stream, entries in msgs:
                for msg_id, fields in entries:
                    raw = fields.get("data")
                    if raw is None:
                        await self._client.xack(stream, group, msg_id)
                        continue
                    try:
                        event = model.model_validate_json(raw)
                    except Exception:
                        # message invalide → ack pour ne pas boucler
                        await self._client.xack(stream, group, msg_id)
                        continue
                    yield msg_id, event
                    await self._client.xack(stream, group, msg_id)

    async def subscribe_pubsub(self, channel: str) -> AsyncIterator[dict]:
        """Pub/sub volatile pour push UI temps réel."""
        await self.connect()
        assert self._client is not None
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def publish_pubsub(self, channel: str, payload: dict) -> None:
        await self.connect()
        assert self._client is not None
        await self._client.publish(channel, json.dumps(payload))
