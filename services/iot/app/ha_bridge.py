"""Bridge Home Assistant via REST."""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("iot.ha")


class HABridge:
    def __init__(self) -> None:
        self.base_url = os.getenv("HA_BASE_URL", "http://homeassistant:8123").rstrip("/")
        self.token = os.getenv("HA_LONG_LIVED_TOKEN", "")

    def _headers(self) -> dict:
        if not self.token:
            raise RuntimeError("HA_LONG_LIVED_TOKEN manquant")
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def call_service(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
        body = {"entity_id": entity_id}
        if data:
            body.update(data)
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                json=body,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_state(self, entity_id: str) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{self.base_url}/api/states/{entity_id}", headers=self._headers()
            )
            r.raise_for_status()
            return r.json()
