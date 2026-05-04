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
    STREAM_INTENT_RESPONSE_PARTIAL,
    STREAM_VOICE_TRANSCRIPT,
    IntentResponse,
    IntentResponsePartial,
    VoiceTranscriptReady,
)

from . import challenge  # noqa: E402
from .identity import IdentityStore, consume_identity_events, consume_liveness_events  # noqa: E402
from .autonomous import is_autonomous_request, run_autonomous  # noqa: E402
from .rag import fetch_relevant_memories, format_context  # noqa: E402
from .skills import registry as skill_registry  # noqa: E402
from .streaming import stream_sentences  # noqa: E402
from .tools import dispatch_tool as legacy_dispatch_tool  # noqa: E402
from .tools.registry import ADMIN_TOOLS as LEGACY_ADMIN_TOOLS  # noqa: E402
from .tools.registry import TOOL_DEFS as LEGACY_TOOL_DEFS  # noqa: E402


def all_tool_defs() -> list[dict]:
    """Combine les tools legacy (iot, memory, security) et ceux des skills."""
    out = list(LEGACY_TOOL_DEFS)
    for t in skill_registry.all_tools():
        out.append({"name": t.name, "description": t.description, "input_schema": t.input_schema})
    return out


def all_admin_tools() -> set[str]:
    out = set(LEGACY_ADMIN_TOOLS)
    for t in skill_registry.all_tools():
        if t.requires_admin:
            out.add(t.name)
    return out


async def dispatch_tool(name: str, arguments: dict, ctx: dict) -> Any:
    """Dispatch unifié : essaie d'abord les skills, sinon retombe sur le legacy."""
    skill_tool = skill_registry.find_tool(name)
    if skill_tool is not None:
        return await skill_tool.handler(arguments, ctx)
    return await legacy_dispatch_tool(
        name, arguments, ctx.get("user_id"), bool(ctx.get("is_owner"))
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("orchestrator")

LLM_URL = "http://llm:8000/complete"
LLM_STREAM_URL = "http://llm:8000/complete/stream"
THRESHOLD_ACCEPT = float(os.getenv("VOICEPRINT_THRESHOLD_ACCEPT", "0.75"))
THRESHOLD_GREY = float(os.getenv("VOICEPRINT_THRESHOLD_GREY", "0.65"))
CHALLENGE_ENABLED = os.getenv("VOICEPRINT_CHALLENGE_ENABLED", "true").lower() == "true"
STREAM_ENABLED = os.getenv("LLM_STREAM_ENABLED", "true").lower() == "true"

# Mémoire courte par session (les N derniers tours)
_HISTORY: dict[str, list[dict]] = {}
HISTORY_MAX = 12

identity_store = IdentityStore()


async def call_llm(messages: list[dict]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            LLM_URL,
            json={"messages": messages, "tools": all_tool_defs(), "max_tokens": 512},
        )
        r.raise_for_status()
        return r.json()


async def stream_llm_tokens(messages: list[dict]) -> "Any":
    """Génère les tokens du LLM en streaming (SSE)."""
    import json as _json

    async def _gen():
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                LLM_STREAM_URL,
                json={"messages": messages, "max_tokens": 512},
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    obj = _json.loads(payload)
                    if obj.get("done"):
                        return
                    if "error" in obj:
                        log.warning("llm stream error: %s", obj["error"])
                        return
                    tok = obj.get("token", "")
                    if tok:
                        yield tok
    return _gen()


async def trace_reasoning(
    session_id: str,
    user_id: str | None,
    user_text: str,
    intent: str,
    tools_called: list[dict],
    memory_hits: list[dict],
    response: str,
    duration_ms: int,
) -> None:
    """Persist trace pour explainability."""
    import json as _json

    import asyncpg

    try:
        pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "jarvis"),
            user=os.getenv("POSTGRES_USER", "jarvis"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=1,
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reasoning_traces(
                    session_id, user_id, user_text, intent,
                    tools_called, memory_hits, response, duration_ms
                ) VALUES($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8)
                """,
                session_id,
                user_id,
                user_text,
                intent,
                _json.dumps(tools_called),
                _json.dumps(memory_hits),
                response,
                duration_ms,
            )
        await pool.close()
    except Exception as e:
        log.warning("trace reasoning failed: %s", e)


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
    if name not in all_admin_tools():
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
            ctx = {
                "session_id": session_id,
                "user_id": user_id,
                "is_owner": is_owner or owner_now,
            }
            result = await dispatch_tool(tc["name"], args, ctx)
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
    import time as _time

    async for _id, ev in bus.consume(
        STREAM_VOICE_TRANSCRIPT, "orch", "orch-1", VoiceTranscriptReady
    ):
        if not ev.text.strip():
            continue
        try:
            owner_now, _ = _resolve_owner_state(ev.session_id)
            t0 = _time.time()
            cur = identity_store.get(ev.session_id)
            user_id = cur.user_id if cur else None
            tools_called: list[dict] = []
            memory_hits: list[dict] = []

            history = _HISTORY.setdefault(ev.session_id, [])

            # Mode agent autonome : si la requête a l'air complexe, on bascule
            # sur le chaînage multi-tools en arrière-plan et on annonce vocalement.
            if is_autonomous_request(ev.text):
                await bus.publish(
                    STREAM_INTENT_RESPONSE,
                    IntentResponse(
                        source="orchestrator",
                        session_id=ev.session_id,
                        text="J'enchaîne plusieurs étapes — je te dis dès que c'est fini.",
                    ),
                )
                ctx_auto = {
                    "session_id": ev.session_id,
                    "user_id": user_id,
                    "is_owner": owner_now,
                }
                result = await run_autonomous(
                    [{"role": "user", "content": ev.text}],
                    call_llm,
                    dispatch_tool,
                    _gate_admin,
                    ctx_auto,
                )
                await bus.publish(
                    STREAM_INTENT_RESPONSE,
                    IntentResponse(
                        source="orchestrator",
                        session_id=ev.session_id,
                        text=result["reply"],
                    ),
                )
                duration_ms = int((_time.time() - t0) * 1000)
                await trace_reasoning(
                    ev.session_id, user_id, ev.text, "autonomous",
                    [{"name": s["tool"], "args": s["args"]} for s in result["steps"]],
                    [], result["reply"], duration_ms,
                )
                continue

            # Memory-augmented prompting : on récupère K souvenirs pertinents
            # et on les injecte comme message system additionnel pour ce tour.
            memories = await fetch_relevant_memories(ev.text, user_id=user_id)
            memory_hits = [
                {"score": m.get("score"), "text": m.get("text"), "id": m.get("id")}
                for m in memories
            ]
            if memories:
                ctx_msg = format_context(memories)
                # injecte au tout début (sans polluer l'historique récurrent)
                history_with_ctx = (
                    [{"role": "system", "content": ctx_msg}] + history + [{"role": "user", "content": ev.text}]
                )
            else:
                history_with_ctx = history + [{"role": "user", "content": ev.text}]
            history.append({"role": "user", "content": ev.text})

            # Si STREAM_ENABLED et pas de tool nécessaire, on streame phrase-par-phrase
            if STREAM_ENABLED:
                token_iter = await stream_llm_tokens(history_with_ctx)
                full_text = ""
                seq = 0
                async for sentence in stream_sentences(token_iter):
                    full_text += sentence + " "
                    await bus.publish(
                        STREAM_INTENT_RESPONSE_PARTIAL,
                        IntentResponsePartial(
                            source="orchestrator",
                            session_id=ev.session_id,
                            text=sentence,
                            seq=seq,
                            is_final=False,
                        ),
                    )
                    seq += 1
                # marqueur final pour fermer le TTS
                await bus.publish(
                    STREAM_INTENT_RESPONSE_PARTIAL,
                    IntentResponsePartial(
                        source="orchestrator",
                        session_id=ev.session_id,
                        text="",
                        seq=seq,
                        is_final=True,
                    ),
                )
                history.append({"role": "assistant", "content": full_text.strip()})
                duration_ms = int((_time.time() - t0) * 1000)
                await trace_reasoning(
                    ev.session_id, user_id, ev.text, "stream", tools_called, memory_hits,
                    full_text.strip(), duration_ms,
                )
            else:
                reply = await run_turn(ev.session_id, user_id, owner_now, ev.text)
                await bus.publish(
                    STREAM_INTENT_RESPONSE,
                    IntentResponse(
                        source="orchestrator", session_id=ev.session_id, text=reply
                    ),
                )
                duration_ms = int((_time.time() - t0) * 1000)
                await trace_reasoning(
                    ev.session_id, user_id, ev.text, "tool_calling",
                    tools_called, memory_hits, reply, duration_ms,
                )
            if len(history) > HISTORY_MAX:
                del history[: len(history) - HISTORY_MAX]
        except Exception as e:
            log.exception("orchestration failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus = EventBus()
    await bus.connect()
    skill_registry.load_builtin()
    skill_registry.load_external("/skills")
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


@app.get("/skills")
async def skills_list() -> dict:
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "tools": [t.name for t in s.tools],
                "crons": [c.name for c in s.crons],
            }
            for s in skill_registry.all_skills()
        ]
    }


@app.post("/skills/reload")
async def skills_reload() -> dict:
    skill_registry.reload()
    return {"status": "reloaded", "count": len(skill_registry.all_skills())}


class AutonomousRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    is_owner: bool = False
    text: str
    max_steps: int = 8


@app.post("/autonomous")
async def autonomous(req: AutonomousRequest) -> dict:
    """Mode agent autonome : enchaîne plusieurs tools jusqu'à atteindre l'objectif."""
    history = [{"role": "user", "content": req.text}]
    ctx = {
        "session_id": req.session_id,
        "user_id": req.user_id,
        "is_owner": req.is_owner,
    }
    out = await run_autonomous(
        history,
        call_llm,
        dispatch_tool,
        _gate_admin,
        ctx,
        max_steps=req.max_steps,
    )
    return out


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
