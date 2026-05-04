"""Bridge zwave-js-ui (anciennement zwavejs2mqtt).

Expose les devices Z-Wave via MQTT sous le topic configurable Z-Wave.
Discovery : appel REST `GET /api/v1/store` ou via le topic
`zwavejs/_CLIENTS/<client>/api/getNodes` (selon version).

Pragmatique : on supporte les 2 modes :
1. Listing des nodes via REST API du frontend zwave-js-ui (port 8091)
2. Subscribe MQTT sur `zwavejs/<nodeID>/<command_class>/<...>`
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine

import httpx
from asyncio_mqtt import Client

log = logging.getLogger("iot.zwave")

OnState = Callable[[str, dict], Coroutine]


class ZWaveBridge:
    def __init__(self) -> None:
        self.host = os.getenv("MQTT_HOST", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.username = os.getenv("MQTT_USERNAME") or None
        self.password = os.getenv("MQTT_PASSWORD") or None
        self.base = os.getenv("ZWAVE_BASE_TOPIC", "zwave")
        self.api_url = os.getenv("ZWAVE_API_URL", "http://zwave-js-ui:8091")
        self.api_token = os.getenv("ZWAVE_API_TOKEN", "")  # facultatif

    async def list_devices(self) -> list[dict]:
        """Liste les nœuds Z-Wave via le frontend zwave-js-ui."""
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as c:
                r = await c.get(f"{self.api_url}/api/v1/nodes")
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            log.warning("Z-Wave list_devices a échoué (%s)", e)
            return []
        out: list[dict] = []
        for n in data.get("data", data) or []:
            node_id = n.get("id") or n.get("nodeId")
            if node_id is None:
                continue
            label = n.get("loc") or n.get("name") or f"node-{node_id}"
            requires_admin = (n.get("deviceClass", {}).get("generic") == "Lock")
            out.append(
                {
                    "id": f"zwave.{node_id}",
                    "name": label,
                    "transport": "mqtt",  # commandes MQTT via zwavejs
                    "config": {
                        "cmd_topic": f"{self.base}/{node_id}/set",
                        "state_topic": f"{self.base}/{node_id}/status",
                        "node_id": node_id,
                        "manufacturer": n.get("manufacturer"),
                        "product": n.get("productLabel"),
                    },
                    "requires_admin": requires_admin,
                }
            )
        return out

    async def command(self, node_id: int | str, action: str, params: dict | None = None) -> None:
        """Publie sur le topic Z-Wave. zwavejs accepte un payload JSON avec valueId."""
        topic = f"{self.base}/{node_id}/set"
        payload = {"action": action, **(params or {})}
        async with Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        ) as client:
            await client.publish(topic, json.dumps(payload).encode("utf-8"))
        log.info("zwave %s ← %s", topic, payload)

    async def subscribe_states(self, on_state: OnState) -> None:
        async with Client(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
        ) as client:
            await client.subscribe(f"{self.base}/+/+/+")
            log.info("zwave subscribe %s/+/+/+", self.base)
            async with client.messages() as messages:
                async for msg in messages:
                    topic = str(msg.topic).split("/")
                    if len(topic) < 3:
                        continue
                    node_id = topic[1]
                    try:
                        payload = json.loads(msg.payload.decode("utf-8"))
                    except Exception:
                        continue
                    await on_state(f"zwave.{node_id}", payload)
