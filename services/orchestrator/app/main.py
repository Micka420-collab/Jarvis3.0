"""Orchestrator : transcript → LLM (avec tools) → réponse → TTS event.

Expose aussi un endpoint REST `/orchestrate` (pour le chat texte du gateway).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_INTENT_RESPONSE,
    STREAM_VOICE_TRANSCRIPT,
    IntentResponse,
    VoiceTranscriptReady,
)

from .tools import TOOL_DEFS, dispatch_tool  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("orchestrator")

LLM_URL = "http://llm:8000/complete"

# Mémoire courte par session (les N derniers tours)
_HISTORY: dict[str, list[dict]] = {}
HISTORY_MAX = 12


async def call_llm(messages: list[dict]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            LLM_URL,
            json={"messages": messages, "tools": TOOL_DEFS, "max_tokens": 512},
        )
        r.raise_for_status()
        return r.json()


async def run_turn(
    session_id: str, user_id: str | None, is_owner: bool, text: str
) -> str:
    history = _HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": text})

    for _ in range(3):  # max 3 boucles tool
        out = await call_llm(history)
        text_out = out.get("text", "")
        tool_calls = out.get("tool_calls", [])

        if not tool_calls:
            history.append({"role": "assistant", "content": text_out})
            break

        history.append({"role": "assistant", "content": text_out, "tool_calls": tool_calls})
        for tc in tool_calls:
            args = tc.get("input") if isinstance(tc.get("input"), dict) else {}
            result = await dispatch_tool(tc["name"], args, user_id, is_owner)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": tc["name"],
                    "content": str(result),
                }
            )

    # tronque historique
    if len(history) > HISTORY_MAX:
        del history[: len(history) - HISTORY_MAX]
    return text_out


async def transcript_loop(bus: EventBus) -> None:
    async for _id, ev in bus.consume(
        STREAM_VOICE_TRANSCRIPT, "orch", "orch-1", VoiceTranscriptReady
    ):
        if not ev.text.strip():
            continue
        try:
            # TODO: enrichir avec is_owner en consommant aussi STREAM_VOICE_IDENTITY
            reply = await run_turn(ev.session_id, None, False, ev.text)
            await bus.publish(
                STREAM_INTENT_RESPONSE,
                IntentResponse(
                    source="orchestrator",
                    session_id=ev.session_id,
                    text=reply,
                ),
            )
        except Exception as e:
            log.exception("orchestration failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus = EventBus()
    await bus.connect()
    task = asyncio.create_task(transcript_loop(bus))
    app.state.bus = bus
    yield
    task.cancel()
    await bus.close()


app = FastAPI(title="Jarvis Orchestrator", version="0.1.0", lifespan=lifespan)


class OrchestrateRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    is_owner: bool = False
    text: str


class OrchestrateResponse(BaseModel):
    session_id: str
    reply: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "orchestrator"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest) -> OrchestrateResponse:
    sid = req.session_id or str(uuid.uuid4())
    reply = await run_turn(sid, req.user_id, req.is_owner, req.text)
    return OrchestrateResponse(session_id=sid, reply=reply)
