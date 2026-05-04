"""WebSocket avatar : push d'événements UI temps réel.

Le frontend ouvre cette WS pour recevoir :
- état "speaking/idle"
- alertes Argus poussées proactivement
- événements vision (visage reconnu)
- état IoT (lumière, volet...)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _shared.bus import EventBus  # noqa: E402

router = APIRouter()
log = logging.getLogger("gateway.ws.avatar")

# Canaux pub/sub à brancher sur l'UI
UI_CHANNELS = ("ui.argus", "ui.iot", "ui.vision", "ui.state")


@router.websocket("/avatar")
async def avatar_ws(ws: WebSocket) -> None:
    await ws.accept()
    bus = EventBus()
    await bus.connect()

    async def relay(channel: str) -> None:
        async for payload in bus.subscribe_pubsub(channel):
            await ws.send_json({"channel": channel, "payload": payload})

    tasks = [asyncio.create_task(relay(c)) for c in UI_CHANNELS]
    try:
        while True:
            # ping périodique pour garder la connexion vivante
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await bus.close()
