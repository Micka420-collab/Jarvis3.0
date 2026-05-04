"""Service security : reçoit les alertes Argus et les pousse en TTS proactif."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_ARGUS_ALERT,
    STREAM_INTENT_RESPONSE,
    ArgusAlert,
    IntentResponse,
)

from .alert_mapper import alert_to_speech  # noqa: E402
from .argus_ws import ArgusClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("security")


class State:
    silence_until: float = 0.0
    last_alert: dict | None = None
    bus: EventBus | None = None
    argus: ArgusClient | None = None


state = State()


async def handle_alert(raw: dict) -> None:
    state.last_alert = raw
    if state.bus is None:
        return
    # historiser
    await state.bus.publish(
        STREAM_ARGUS_ALERT,
        ArgusAlert(
            source="security",
            severity=raw.get("severity", "info"),
            rule=raw.get("rule", ""),
            host=raw.get("host", ""),
            summary=raw.get("summary", ""),
            raw=raw,
        ),
    )
    # push UI
    await state.bus.publish_pubsub("ui.argus", raw)
    # TTS proactif (sauf silence)
    if time.time() < state.silence_until:
        return
    speech = alert_to_speech(raw)
    await state.bus.publish(
        STREAM_INTENT_RESPONSE,
        IntentResponse(
            source="security",
            session_id=str(uuid.uuid4()),
            text=speech,
            emotion="alert",
            proactive=True,
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.bus = EventBus()
    await state.bus.connect()
    state.argus = ArgusClient(handle_alert)
    task = asyncio.create_task(state.argus.run())
    yield
    task.cancel()
    if state.bus:
        await state.bus.close()


app = FastAPI(title="Jarvis Security", version="0.1.0", lifespan=lifespan)


class SilenceRequest(BaseModel):
    duration_minutes: int = 30


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "security"}


@app.get("/status")
async def status_route() -> dict:
    return {
        "connected": bool(state.argus and state.argus.connected),
        "silenced": time.time() < state.silence_until,
        "silence_remaining_s": max(0, int(state.silence_until - time.time())),
        "last_alert": state.last_alert,
    }


@app.post("/silence")
async def silence_route(req: SilenceRequest) -> dict:
    state.silence_until = time.time() + req.duration_minutes * 60
    return {"silenced_until": state.silence_until}


@app.post("/test/alert")
async def test_alert(payload: dict) -> dict:
    """Injecter une alerte fictive pour les tests E2E."""
    await handle_alert(payload)
    return {"status": "queued"}
