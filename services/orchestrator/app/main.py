"""Orchestrator : transcript → LLM (avec tools) → réponse → TTS event.

- Consomme aussi `voice.identity.verified` pour gater les admin tools (voix-print)
- Émet une challenge phrase dynamique si un admin tool est demandé sans verif suffisante

Expose aussi un endpoint REST `/orchestrate` (pour le chat texte du gateway).
"""

from __future__ import annotations

import asyncio
import logging
import os
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

from . import challenge  # noqa: E402
from .identity import IdentityStore, consume_identity_events, consume_liveness_events  # noqa: E402
from .tools import TOOL_DEFS, dispatch_tool  # noqa: E402
from .tools.registry import ADMIN_TOOLS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("orchestrator")

LLM_URL = "http://llm:8000/complete"
THRESHOLD_ACCEPT = float(os.getenv("VOICEPRINT_THRESHOLD_ACCEPT", "0.75"))
THRESHOLD_GREY = float(os.getenv("VOICEPRINT_THRESHOLD_GREY", "0.65"))
CHALLENGE_ENABLED = os.getenv("VOICEPRINT_CHALLENGE_ENABLED", "true").lower() == "true"

# Mémoire courte par session (les N derniers tours)
_HISTORY: dict[str, list[dict]] = {}
HISTORY_MAX = 12

identity_store = IdentityStore()


async def call_llm(messages: list[dict]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            LLM_URL,
            json={"messages": messages, "tools": TOOL_DEFS, "max_tokens": 512},
        )
        r.raise_for_status()
        return r.json()


def _resolve_owner_state(session_id: str) -> tuple[bool, float]:
    cur = identity_store.get(session_id)
    if cur is None:
        return False, 0.0
    return cur.is_owner, cur.similarity


def _gate_admin(session_id: str, name: str) -> tuple[bool, str | None]:
    """Retourne (autorisé, phrase_challenge_si_besoin).

    Politique pour les admin tools :
    1. La voix doit être considérée comme humaine (AASIST liveness) si activée.
    2. La similarité voix-print doit être ≥ accept, sinon zone grise → challenge.
    3. Si challenge déjà passé dans cette session, accepté.
    """
    if name not in ADMIN_TOOLS:
        return True, None
    cur = identity_store.get(session_id)
    if cur is None:
        return False, None
    # liveness: si AASIST a tourné et a rejeté, on bloque dur (pas de challenge)
    if not cur.is_human:
        return False, None
    if cur.similarity >= THRESHOLD_ACCEPT and cur.is_owner:
        return True, None
    if (
        CHALLENGE_ENABLED
        and cur.is_owner
        and cur.similarity >= THRESHOLD_GREY
    ):
        if cur.challenge_passed:
            return True, None
        # émettre une challenge phrase
        phrase = challenge.issue(session_id)
        return False, phrase
    return False, None


async def run_turn(
    session_id: str, user_id: str | None, is_owner: bool, text: str
) -> str:
    # 1) Si une challenge phrase est pendante, on tente de la valider
    pending = challenge.has_pending(session_id)
    if pending and challenge.verify(session_id, text):
        identity_store.mark_challenge_passed(session_id)
        return "Identité confirmée. Quelle est ta commande ?"

    history = _HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": text})

    text_out = ""
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
            allowed, challenge_phrase = _gate_admin(session_id, tc["name"])
            if not allowed:
                if challenge_phrase:
                    text_out = (
                        f"Pour cette action, j'ai besoin de vérifier ta voix. "
                        f"Répète exactement : {challenge_phrase}."
                    )
                    history.append({"role": "assistant", "content": text_out})
                    return text_out
                text_out = "Cette action est réservée à mon créateur."
                history.append({"role": "assistant", "content": text_out})
                return text_out

            owner_now, _ = _resolve_owner_state(session_id)
            result = await dispatch_tool(tc["name"], args, user_id, is_owner or owner_now)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": tc["name"],
                    "content": str(result),
                }
            )

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
            owner_now, _ = _resolve_owner_state(ev.session_id)
            reply = await run_turn(ev.session_id, None, owner_now, ev.text)
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
    transcript_task = asyncio.create_task(transcript_loop(bus))
    identity_task = asyncio.create_task(consume_identity_events(bus, identity_store))
    liveness_task = asyncio.create_task(consume_liveness_events(bus, identity_store))
    app.state.bus = bus
    yield
    transcript_task.cancel()
    identity_task.cancel()
    liveness_task.cancel()
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


@app.get("/identity")
async def identity(session_id: str) -> dict:
    cur = identity_store.get(session_id)
    if cur is None:
        return {"authenticated": False, "is_owner": False, "similarity": 0.0}
    is_authed = cur.is_owner and (
        cur.similarity >= THRESHOLD_ACCEPT
        or (cur.similarity >= THRESHOLD_GREY and cur.challenge_passed)
    )
    return {
        "authenticated": is_authed,
        "is_owner": cur.is_owner,
        "similarity": cur.similarity,
        "challenge_passed": cur.challenge_passed,
        "user_id": cur.user_id,
    }
