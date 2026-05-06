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

    async def list_entities(
        self, domains: tuple[str, ...] = ("light", "switch", "cover", "sensor", "lock")
    ) -> list[dict]:
        """Récupère toutes les entités HA des domaines fournis (HA discovery)."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/api/states", headers=self._headers())
            r.raise_for_status()
            states = r.json()
        out = []
        for s in states:
            entity_id = s.get("entity_id", "")
            if not entity_id:
                continue
            domain = entity_id.split(".", 1)[0]
            if domain not in domains:
                continue
            attrs = s.get("attributes") or {}
            out.append(
                {
                    "id": entity_id,
                    "name": attrs.get("friendly_name") or entity_id,
                    "transport": "homeassistant",
                    "config": {"entity_id": entity_id},
                    "requires_admin": domain == "lock",
                    "current_state": s.get("state"),
                }
            )
        return out
