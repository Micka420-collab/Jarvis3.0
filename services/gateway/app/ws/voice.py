"""WebSocket voix bidirectionnelle.

Protocole client → serveur :
  {"type": "audio", "pcm_b64": "...", "seq": N}    # PCM 16-bit mono 16 kHz
  {"type": "end"}                                   # marque fin d'utterance
  {"type": "text", "text": "..."}                   # bypass STT (debug)

Protocole serveur → client :
  {"type": "transcript", "text": "..."}
  {"type": "identity", "is_owner": true, "similarity": 0.82}
  {"type": "tts_chunk", "pcm_b64": "...", "viseme": "AA", "is_final": false}
  {"type": "error", "detail": "..."}

Le gateway forwarde les chunks audio vers le service voice via le bus Redis,
et restitue les transcripts/TTS produits par le pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Permet d'importer services/_shared/* depuis le container (monté en /app/_shared)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_VOICE_AUDIO_CHUNK,
    STREAM_VOICE_TRANSCRIPT,
    STREAM_VOICE_TRANSCRIPT_PARTIAL,
    STREAM_TTS_AUDIO_CHUNK,
    VoiceAudioChunk,
    VoiceTranscriptReady,
    VoiceTranscriptPartial,
    TtsAudioChunk,
)

router = APIRouter()
log = logging.getLogger("gateway.ws.voice")


@router.websocket("/voice")
async def voice_ws(ws: WebSocket) -> None:
    await ws.accept()
    session_id = str(uuid.uuid4())
    bus = EventBus()
    await bus.connect()
    log.info("voice WS session=%s", session_id)
    await ws.send_json({"type": "session", "session_id": session_id})

    async def forward_transcripts() -> None:
        async for _id, ev in bus.consume(
            STREAM_VOICE_TRANSCRIPT, f"gw-{session_id}", "gw", VoiceTranscriptReady
        ):
            if ev.session_id != session_id:
                continue
            await ws.send_json({"type": "transcript", "text": ev.text, "lang": ev.lang})

    async def forward_partials() -> None:
        async for _id, ev in bus.consume(
            STREAM_VOICE_TRANSCRIPT_PARTIAL,
            f"gw-partial-{session_id}",
            "gw",
            VoiceTranscriptPartial,
        ):
            if ev.session_id != session_id:
                continue
            await ws.send_json(
                {"type": "transcript_partial", "text": ev.text, "lang": ev.lang}
            )

    async def forward_tts() -> None:
        async for _id, ev in bus.consume(
            STREAM_TTS_AUDIO_CHUNK, f"gw-tts-{session_id}", "gw", TtsAudioChunk
        ):
            if ev.session_id != session_id:
                continue
            await ws.send_json(
                {
                    "type": "tts_chunk",
                    "pcm_b64": ev.pcm_b64,
                    "seq": ev.seq,
                    "is_final": ev.is_final,
                    "viseme": ev.viseme,
                }
            )

    transcripts_task = asyncio.create_task(forward_transcripts())
    partials_task = asyncio.create_task(forward_partials())
    tts_task = asyncio.create_task(forward_tts())

    try:
        seq = 0
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            if mtype == "audio":
                ev = VoiceAudioChunk(
                    source="gateway",
                    session_id=session_id,
                    pcm_b64=msg["pcm_b64"],
                    seq=seq,
                )
                seq += 1
                await bus.publish(STREAM_VOICE_AUDIO_CHUNK, ev)
            elif mtype == "end":
                # forcing utterance flush via stream marker
                ev = VoiceAudioChunk(
                    source="gateway",
                    session_id=session_id,
                    pcm_b64="",
                    seq=seq,
                )
                await bus.publish(STREAM_VOICE_AUDIO_CHUNK, ev)
                seq = 0
            elif mtype == "text":
                # bypass STT : injecte directement un transcript
                tev = VoiceTranscriptReady(
                    source="gateway",
                    session_id=session_id,
                    text=msg["text"],
                    lang="fr",
                    confidence=1.0,
                )
                await bus.publish(STREAM_VOICE_TRANSCRIPT, tev)
            else:
                await ws.send_json({"type": "error", "detail": f"type inconnu: {mtype}"})
    except WebSocketDisconnect:
        pass
    finally:
        transcripts_task.cancel()
        partials_task.cancel()
        tts_task.cancel()
        await bus.close()
        log.info("voice WS close session=%s", session_id)
