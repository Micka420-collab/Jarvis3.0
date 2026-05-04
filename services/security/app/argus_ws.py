"""Client WebSocket vers Argus avec auth JWT et reconnexion auto."""

from __future__ import annotations

import asyncio
import json
import logging
import os

import websockets

log = logging.getLogger("security.argus")


class ArgusClient:
    def __init__(self, on_alert) -> None:
        self.url = os.getenv("ARGUS_WS_URL", "")
        self.token = os.getenv("ARGUS_API_TOKEN", "")
        self.on_alert = on_alert
        self.connected = False

    async def run(self) -> None:
        if not self.url:
            log.warning("ARGUS_WS_URL vide — client désactivé")
            return
        backoff = 1.0
        while True:
            try:
                headers = {}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                async with websockets.connect(self.url, additional_headers=headers) as ws:
                    self.connected = True
                    log.info("argus connecté: %s", self.url)
                    backoff = 1.0
                    async for msg in ws:
                        try:
                            payload = json.loads(msg)
                            await self.on_alert(payload)
                        except Exception as e:
                            log.warning("alerte invalide: %s", e)
            except Exception as e:
                self.connected = False
                log.warning("argus déconnecté (%s) — retry %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
