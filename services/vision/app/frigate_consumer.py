"""Consomme les événements Frigate (WS) et déclenche la reconnaissance faciale.

Note : pour tirer une frame on appelle l'API Frigate `/api/<camera>/latest.jpg`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx
import numpy as np
import websockets

log = logging.getLogger("vision.frigate")


class FrigateConsumer:
    def __init__(self, on_frame) -> None:
        self.ws_url = os.getenv("FRIGATE_WS_URL", "")
        self.api_url = os.getenv("FRIGATE_API_URL", "")
        self.on_frame = on_frame

    async def fetch_frame(self, camera: str) -> np.ndarray | None:
        if not self.api_url:
            return None
        import cv2

        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{self.api_url}/api/{camera}/latest.jpg")
            if r.status_code != 200:
                return None
            arr = np.frombuffer(r.content, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    async def run(self) -> None:
        if not self.ws_url:
            log.warning("FRIGATE_WS_URL vide — consumer désactivé")
            return
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    log.info("frigate connecté")
                    backoff = 1.0
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            if msg.get("type") != "new":
                                continue
                            camera = msg.get("after", {}).get("camera")
                            if not camera:
                                continue
                            frame = await self.fetch_frame(camera)
                            if frame is not None:
                                await self.on_frame(camera, frame)
                        except Exception as e:
                            log.warning("event KO: %s", e)
            except Exception as e:
                log.warning("frigate déconnecté (%s) — retry %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
