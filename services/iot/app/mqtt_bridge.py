"""Bridge MQTT (Mosquitto)."""

from __future__ import annotations

import json
import logging
import os

from asyncio_mqtt import Client

log = logging.getLogger("iot.mqtt")


class MQTTBridge:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.username = os.getenv("MQTT_USERNAME") or None
        self.password = os.getenv("MQTT_PASSWORD") or None

    async def publish(self, topic: str, payload: dict) -> None:
        async with Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        ) as client:
            await client.publish(topic, json.dumps(payload).encode("utf-8"))
            log.info("mqtt publish %s payload=%s", topic, payload)
