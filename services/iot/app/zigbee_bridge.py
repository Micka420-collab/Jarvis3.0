"""Bridge Zigbee2MQTT.

Z2M publie chaque appareil sur le topic `zigbee2mqtt/<device_friendly_name>`
avec un payload JSON complet (state, brightness, sensors, etc).
La liste des devices est exposée sur `zigbee2mqtt/bridge/devices` (rétention).

Ce bridge :
- Découvre la liste Z2M et l'expose en `/discover/zigbee` (sync table devices Postgres)
- Mappe nos commandes (`on`, `off`, `toggle`, `set`) vers le format Z2M attendu
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine

import httpx
from asyncio_mqtt import Client

log = logging.getLogger("iot.zigbee")

OnState = Callable[[str, dict], Coroutine]


class Z2MBridge:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.username = os.getenv("MQTT_USERNAME") or None
        self.password = os.getenv("MQTT_PASSWORD") or None
        self.base = os.getenv("Z2M_BASE_TOPIC", "zigbee2mqtt")
        self.frontend_url = os.getenv("Z2M_FRONTEND_URL", "http://zigbee2mqtt:8080")

    # ---- Commandes ----
    @staticmethod
    def _cmd_payload(action: str, params: dict) -> dict:
        if action in ("on", "off"):
            return {"state": action.upper()}
        if action == "toggle":
            return {"state": "TOGGLE"}
        if action == "set":
            return params
        if action in ("open", "close", "stop"):
            return {"state": action.upper()}
        return params

    async def command(self, friendly_name: str, action: str, params: dict | None = None) -> None:
        topic = f"{self.base}/{friendly_name}/set"
        payload = self._cmd_payload(action, params or {})
        async with Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        ) as client:
            await client.publish(topic, json.dumps(payload).encode("utf-8"))
        log.info("z2m %s ← %s", topic, payload)

    # ---- Discovery ----
    async def list_devices(self) -> list[dict]:
        """Demande la liste des devices à Z2M via REST sur le frontend."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{self.frontend_url}/api/devices")
            r.raise_for_status()
            data = r.json()
        out = []
        for d in data:
            if d.get("type") == "Coordinator":
                continue
            friendly = d.get("friendly_name") or d.get("ieee_address")
            if not friendly:
                continue
            definition = d.get("definition") or {}
            description = definition.get("description") or definition.get("model") or "Zigbee device"
            requires_admin = bool(d.get("requires_admin")) or "lock" in description.lower()
            out.append(
                {
                    "id": f"z2m.{friendly}",
                    "name": friendly,
                    "transport": "zigbee2mqtt",
                    "config": {
                        "friendly_name": friendly,
                        "model": definition.get("model"),
                        "vendor": definition.get("vendor"),
                    },
                    "requires_admin": requires_admin,
                }
            )
        return out

    # ---- States stream ----
    async def subscribe_states(self, on_state: OnState) -> None:
        """Écoute `zigbee2mqtt/<friendly>` (hors topics système) et publie."""
        sys_prefix = (f"{self.base}/bridge", f"{self.base}/groups")
        async with Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        ) as client:
            await client.subscribe(f"{self.base}/#")
            log.info("z2m subscribe %s/#", self.base)
            async with client.messages() as messages:
                async for msg in messages:
                    topic = str(msg.topic)
                    if any(topic.startswith(p) for p in sys_prefix):
                        continue
                    if "/" not in topic:
                        continue
                    parts = topic.split("/", 2)
                    # zigbee2mqtt/<friendly>  ou  zigbee2mqtt/<friendly>/availability
                    friendly = parts[1] if len(parts) > 1 else None
                    if not friendly or len(parts) > 2:
                        continue
                    try:
                        payload = json.loads(msg.payload.decode("utf-8"))
                    except Exception:
                        continue
                    await on_state(f"z2m.{friendly}", payload)
