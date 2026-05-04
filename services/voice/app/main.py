"""Boucle principale du service voice.

- Consomme `voice.audio.chunk` → VAD silero → STT → publie `voice.transcript.ready`
- Compare embedding voix à l'owner stocké en pgvector → publie `voice.identity.verified`
- Consomme `intent.response.ready` → TTS streaming → publie `tts.audio.chunk` (avec viseme)
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

from .visemes import amplitude_to_jaw  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("voice")


def make_tts():
    provider = os.getenv("TTS_PROVIDER", "piper").lower()
    if provider == "elevenlabs":
        from .tts_eleven import ElevenLabsTTS

        return ElevenLabsTTS()
    from .tts_piper import PiperTTS

    return PiperTTS()


# ---------------------------------------------------------------------------
# Voix-print : charge l'embedding owner depuis Postgres
# ---------------------------------------------------------------------------


class OwnerStore:
    def __init__(self) -> None:
        self.pool = None
        self.owner_id: str | None = None
        self.owner_embedding = None

    async def connect(self) -> None:
        import asyncpg
        import numpy as np

        self.pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "jarvis"),
            user=os.getenv("POSTGRES_USER", "jarvis"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=2,
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, v.embedding::text AS emb
                  FROM voiceprints v
                  JOIN users u ON u.id = v.user_id
                 WHERE u.is_owner = TRUE
              ORDER BY v.updated_at DESC
                 LIMIT 1
                """
            )
        if row is None:
            log.warning("aucun owner enrôlé — verif voix-print désactivée")
            return
        self.owner_id = str(row["id"])
        # pgvector renvoie une string '[0.1,0.2,...]'
        text = row["emb"].strip("[]")
        self.owner_embedding = np.array([float(x) for x in text.split(",")], dtype=np.float32)
        log.info("owner voiceprint chargé: id=%s dim=%d", self.owner_id, self.owner_embedding.shape[0])


async def stt_loop(bus: EventBus) -> None:
    """Buffer audio par session → VAD → STT à chaque utterance."""
    from .stt_whisper import WhisperSTT
    from .vad import VAD, StreamSegmenter

    stt = WhisperSTT()
    vad = VAD()
    try:
        from .voiceprint import VoiceprintEngine

        vp = VoiceprintEngine()
    except Exception as e:
        log.warning("voiceprint indisponible (%s)", e)
        vp = None

    owner_store = OwnerStore()
    try:
        await owner_store.connect()
    except Exception as e:
        log.warning("owner store indisponible (%s)", e)

    threshold_accept = float(os.getenv("VOICEPRINT_THRESHOLD_ACCEPT", "0.75"))

    segmenters: dict[str, StreamSegmenter] = defaultdict(lambda: StreamSegmenter(vad))

    async def emit_utterance(session_id: str, pcm: bytes) -> None:
        if not pcm or len(pcm) < 8_000:  # < 0.25s
            return
        text, conf = await asyncio.to_thread(stt.transcribe, pcm)
        log.info(
            "transcript session=%s dur_ms=%d conf=%.2f text=%s",
            session_id,
            len(pcm) // 32,
            conf,
            text,
        )
        if not text:
            return
        await bus.publish(
            STREAM_VOICE_TRANSCRIPT,
            VoiceTranscriptReady(
                source="voice", session_id=session_id, text=text, confidence=conf
            ),
        )
        if vp is not None:
            try:
                emb = await asyncio.to_thread(vp.embed, pcm)
                similarity = 0.0
                is_owner = False
                user_id: str | None = None
                if owner_store.owner_embedding is not None:
                    similarity = vp.similarity(emb, owner_store.owner_embedding)
                    is_owner = similarity >= threshold_accept
                    if is_owner:
                        user_id = owner_store.owner_id
                await bus.publish(
                    STREAM_VOICE_IDENTITY,
                    VoiceIdentityVerified(
                        source="voice",
                        session_id=session_id,
                        user_id=user_id,
                        similarity=float(similarity),
                        is_owner=is_owner,
                    ),
                )
            except Exception as e:
                log.warning("voiceprint failed: %s", e)

    async for _id, ev in bus.consume(
        STREAM_VOICE_AUDIO_CHUNK, "voice-stt", "voice-stt-1", VoiceAudioChunk
    ):
        try:
            seg = segmenters[ev.session_id]
            if ev.pcm_b64:
                pcm = base64.b64decode(ev.pcm_b64)
                for utterance in seg.push(pcm):
                    await emit_utterance(ev.session_id, utterance)
                continue
            # marker fin → flush
            tail = seg.flush()
            if tail:
                await emit_utterance(ev.session_id, tail)
            segmenters.pop(ev.session_id, None)
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
                # Si l'adapter ne fournit pas de viseme, on calcule l'amplitude pour piloter la mâchoire.
                if viseme is None:
                    jaw = amplitude_to_jaw(chunk)
                    viseme = "aa" if jaw > 0.6 else ("E" if jaw > 0.3 else "sil")
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
                    viseme="sil",
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
