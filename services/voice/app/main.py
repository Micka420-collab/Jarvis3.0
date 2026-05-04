"""Boucle principale du service voice.

- Consomme `voice.audio.chunk` → buffer + VAD → STT → publie `voice.transcript.ready`
- Si owner_username configuré : extrait embedding voix-print → publie `voice.identity.verified`
- Consomme `intent.response.ready` → TTS streaming → publie `tts.audio.chunk`
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

# Permet d'importer services/_shared/* (monté en /app/_shared)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_INTENT_RESPONSE,
    STREAM_TTS_AUDIO_CHUNK,
    STREAM_VOICE_AUDIO_CHUNK,
    STREAM_VOICE_IDENTITY,
    STREAM_VOICE_TRANSCRIPT,
    IntentResponse,
    TtsAudioChunk,
    VoiceAudioChunk,
    VoiceIdentityVerified,
    VoiceTranscriptReady,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("voice")


def make_tts():
    provider = os.getenv("TTS_PROVIDER", "piper").lower()
    if provider == "elevenlabs":
        from .tts_eleven import ElevenLabsTTS

        return ElevenLabsTTS()
    from .tts_piper import PiperTTS

    return PiperTTS()


async def stt_loop(bus: EventBus) -> None:
    """Buffer audio par session puis STT à la marque de fin."""
    from .stt_whisper import WhisperSTT

    stt = WhisperSTT()
    try:
        from .voiceprint import VoiceprintEngine

        vp = VoiceprintEngine()
    except Exception as e:
        log.warning("voiceprint indisponible (%s)", e)
        vp = None

    buffers: dict[str, list[bytes]] = defaultdict(list)

    async for _id, ev in bus.consume(
        STREAM_VOICE_AUDIO_CHUNK, "voice-stt", "voice-stt-1", VoiceAudioChunk
    ):
        try:
            if ev.pcm_b64:
                buffers[ev.session_id].append(base64.b64decode(ev.pcm_b64))
                continue
            # marker fin d'utterance
            pcm = b"".join(buffers.pop(ev.session_id, []))
            if not pcm:
                continue
            text, conf = await asyncio.to_thread(stt.transcribe, pcm)
            log.info("transcript session=%s len=%d conf=%.2f text=%s", ev.session_id, len(pcm), conf, text)
            await bus.publish(
                STREAM_VOICE_TRANSCRIPT,
                VoiceTranscriptReady(
                    source="voice", session_id=ev.session_id, text=text, confidence=conf
                ),
            )
            if vp is not None and len(pcm) > 16_000:  # > 1s
                emb = await asyncio.to_thread(vp.embed, pcm)
                # TODO: comparer à l'embedding owner stocké en Postgres pgvector
                # Pour le squelette : on publie un event neutre.
                await bus.publish(
                    STREAM_VOICE_IDENTITY,
                    VoiceIdentityVerified(
                        source="voice",
                        session_id=ev.session_id,
                        user_id=None,
                        similarity=0.0,
                        is_owner=False,
                    ),
                )
        except Exception as e:
            log.exception("STT loop error: %s", e)


async def tts_loop(bus: EventBus) -> None:
    tts = make_tts()
    async for _id, ev in bus.consume(
        STREAM_INTENT_RESPONSE, "voice-tts", "voice-tts-1", IntentResponse
    ):
        try:
            log.info("tts session=%s text=%s", ev.session_id, ev.text[:80])
            seq = 0
            async for chunk, viseme in tts.synthesize_stream(ev.text):
                await bus.publish(
                    STREAM_TTS_AUDIO_CHUNK,
                    TtsAudioChunk(
                        source="voice",
                        session_id=ev.session_id,
                        pcm_b64=base64.b64encode(chunk).decode("ascii"),
                        seq=seq,
                        is_final=False,
                        viseme=viseme,
                    ),
                )
                seq += 1
            await bus.publish(
                STREAM_TTS_AUDIO_CHUNK,
                TtsAudioChunk(
                    source="voice",
                    session_id=ev.session_id,
                    pcm_b64="",
                    seq=seq,
                    is_final=True,
                ),
            )
        except Exception as e:
            log.exception("TTS loop error: %s", e)


async def main() -> None:
    bus = EventBus()
    await bus.connect()
    log.info("voice service ready")
    await asyncio.gather(stt_loop(bus), tts_loop(bus))


if __name__ == "__main__":
    asyncio.run(main())
