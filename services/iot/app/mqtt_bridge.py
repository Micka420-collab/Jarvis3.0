"""Bridge MQTT (Mosquitto). Publie les commandes et écoute les states."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine

from asyncio_mqtt import Client

log = logging.getLogger("iot.mqtt")

OnState = Callable[[str, dict], Coroutine]


class MQTTBridge:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.username = os.getenv("MQTT_USERNAME") or None
        self.password = os.getenv("MQTT_PASSWORD") or None
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> Client:
        if self._client is None:
            self._client = Client(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )
            await self._client.__aenter__()
        return self._client

    async def publish(self, topic: str, payload: dict) -> None:
        async with self._lock:
            client = await self._ensure()
            await client.publish(topic, json.dumps(payload).encode("utf-8"))
        log.info("mqtt publish %s payload=%s", topic, payload)

    async def subscribe_states(
        self, topics: list[tuple[str, str]], on_state: OnState
    ) -> None:
        """topics = [(device_id, state_topic), ...]."""
        if not topics:
            return
        client = await self._ensure()
        topic_to_device = {t: d for d, t in topics}
        for d, t in topics:
            await client.subscribe(t)
            log.info("mqtt subscribe %s (device=%s)", t, d)
        async with client.messages() as messages:
            async for msg in messages:
                topic = str(msg.topic)
                device_id = topic_to_device.get(topic)
                if not device_id:
                    continue
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                except Exception:
                    payload = {"raw": msg.payload.decode("utf-8", errors="replace")}
                await on_state(device_id, payload)
