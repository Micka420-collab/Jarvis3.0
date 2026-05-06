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
    STREAM_INTENT_RESPONSE_PARTIAL,
    STREAM_TTS_AUDIO_CHUNK,
    STREAM_VOICE_AUDIO_CHUNK,
    STREAM_VOICE_BARGE_IN,
    STREAM_VOICE_IDENTITY,
    STREAM_VOICE_LIVENESS,
    STREAM_VOICE_TRANSCRIPT,
    STREAM_VOICE_TRANSCRIPT_PARTIAL,
    IntentResponse,
    IntentResponsePartial,
    TtsAudioChunk,
    VoiceAudioChunk,
    VoiceBargeIn,
    VoiceIdentityVerified,
    VoiceLivenessChecked,
    VoiceTranscriptPartial,
    VoiceTranscriptReady,
)

from .multiroom import SpeakerRouter, push_to_speaker  # noqa: E402
from .visemes import amplitude_to_jaw  # noqa: E402

speaker_router = SpeakerRouter()

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


class FamilyVoiceStore:
    """Charge tous les voiceprints des membres de la famille pour le matching multi-utilisateurs."""

    def __init__(self) -> None:
        self.pool = None
        # liste de tuples (user_id, username, is_owner, role, embedding)
        self.members: list[tuple[str, str, bool, str, "np.ndarray"]] = []

    async def connect(self) -> None:
        import asyncpg
        import numpy as np  # noqa: F401

        self.pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "jarvis"),
            user=os.getenv("POSTGRES_USER", "jarvis"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=2,
        )
        await self.refresh()

    async def refresh(self) -> None:
        import numpy as np

        if self.pool is None:
            return
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.id, u.username, u.is_owner, u.role, v.embedding::text AS emb
                  FROM voiceprints v
                  JOIN users u ON u.id = v.user_id
                """
            )
        members = []
        for r in rows:
            text = r["emb"].strip("[]")
            emb = np.array([float(x) for x in text.split(",")], dtype=np.float32)
            members.append((str(r["id"]), r["username"], r["is_owner"], r["role"], emb))
        self.members = members
        log.info("family voiceprints chargés: %d membres", len(members))

    def best_match(self, embedding: "np.ndarray") -> tuple[str | None, str | None, bool, str, float]:
        """Retourne (user_id, username, is_owner, role, similarity)."""
        import numpy as np

        best = (None, None, False, "guest", 0.0)
        for uid, uname, owner, role, ref in self.members:
            sim = float(np.dot(embedding, ref))
            if sim > best[4]:
                best = (uid, uname, owner, role, sim)
        return best


# alias rétro-compat
OwnerStore = FamilyVoiceStore


async def stt_loop(bus: EventBus) -> None:
    """Buffer audio par session → VAD → STT (partial à chaque ~700 ms + final à fin d'utterance)."""
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

    try:
        from .liveness import LivenessChecker

        liveness = LivenessChecker()
    except Exception as e:
        log.info("liveness AASIST indisponible (%s) — désactivée", e)
        liveness = None

    owner_store = OwnerStore()
    try:
        await owner_store.connect()
    except Exception as e:
        log.warning("owner store indisponible (%s)", e)

    threshold_accept = float(os.getenv("VOICEPRINT_THRESHOLD_ACCEPT", "0.75"))
    partial_every_bytes = int(os.getenv("STT_PARTIAL_EVERY_MS", "700")) * 32  # 16k * 2 bytes / 1000ms
    last_partial_text: dict[str, str] = {}

    segmenters: dict[str, StreamSegmenter] = defaultdict(lambda: StreamSegmenter(vad))
    accumulators: dict[str, bytearray] = defaultdict(bytearray)

    async def emit_partial(session_id: str, pcm: bytes) -> None:
        if not pcm or len(pcm) < 8_000:  # < 0.25s
            return
        text, _conf = await asyncio.to_thread(stt.transcribe, pcm)
        text = text.strip()
        if not text:
            return
        # barge-in : si un TTS est en cours et qu'on entend l'utilisateur, on le coupe
        if not _barge_event(session_id).is_set():
            await bus.publish(
                STREAM_VOICE_BARGE_IN, VoiceBargeIn(source="voice", session_id=session_id)
            )
        if last_partial_text.get(session_id) == text:
            return
        last_partial_text[session_id] = text
        await bus.publish(
            STREAM_VOICE_TRANSCRIPT_PARTIAL,
            VoiceTranscriptPartial(
                source="voice", session_id=session_id, text=text, is_stable=False
            ),
        )

    async def emit_utterance(session_id: str, pcm: bytes) -> None:
        last_partial_text.pop(session_id, None)
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
        if liveness is not None:
            try:
                lv = await asyncio.to_thread(liveness.score, pcm)
                await bus.publish(
                    STREAM_VOICE_LIVENESS,
                    VoiceLivenessChecked(
                        source="voice",
                        session_id=session_id,
                        score=float(lv.score),
                        is_human=bool(lv.is_human),
                        threshold=float(lv.threshold),
                    ),
                )
            except Exception as e:
                log.warning("liveness failed: %s", e)
        if vp is not None:
            try:
                emb = await asyncio.to_thread(vp.embed, pcm)
                user_id, _username, is_owner_match, _role, similarity = owner_store.best_match(emb)
                # owner si match sur user_id is_owner ET seuil dépassé
                is_owner_authed = bool(is_owner_match) and similarity >= threshold_accept
                # si la similarité est faible, on n'attribue pas la session à un user
                if similarity < float(os.getenv("VOICEPRINT_THRESHOLD_GREY", "0.65")):
                    user_id = None
                await bus.publish(
                    STREAM_VOICE_IDENTITY,
                    VoiceIdentityVerified(
                        source="voice",
                        session_id=session_id,
                        user_id=user_id,
                        similarity=float(similarity),
                        is_owner=is_owner_authed,
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
                # finalize utterances détectées par le VAD
                for utterance in seg.push(pcm):
                    await emit_utterance(ev.session_id, utterance)
                # accumule pour les transcripts partiels (rolling buffer)
                if seg._in_speech:  # type: ignore[attr-defined]
                    accumulators[ev.session_id].extend(seg._utterance)  # type: ignore[attr-defined]
                    if len(accumulators[ev.session_id]) >= partial_every_bytes:
                        # déclenche un partial mais sans bloquer la consommation
                        snapshot = bytes(seg._utterance)  # type: ignore[attr-defined]
                        accumulators[ev.session_id].clear()
                        asyncio.create_task(emit_partial(ev.session_id, snapshot))
                continue
            # marker fin → flush
            tail = seg.flush()
            if tail:
                await emit_utterance(ev.session_id, tail)
            segmenters.pop(ev.session_id, None)
            accumulators.pop(ev.session_id, None)
        except Exception as e:
            log.exception("STT loop error: %s", e)


_BARGE_IN: dict[str, asyncio.Event] = {}


def _barge_event(session_id: str) -> asyncio.Event:
    ev = _BARGE_IN.get(session_id)
    if ev is None:
        ev = asyncio.Event()
        _BARGE_IN[session_id] = ev
    return ev


async def _tts_one(bus: EventBus, tts, session_id: str, text: str, is_final: bool, base_seq: int) -> int:
    """Synthétise un texte et stream les chunks. Coupe si barge-in déclenché."""
    seq = base_seq
    barge = _barge_event(session_id)
    async for chunk, viseme in tts.synthesize_stream(text):
        if barge.is_set():
            log.info("tts barge-in session=%s — stop synthesis", session_id)
            break
        if viseme is None:
            jaw = amplitude_to_jaw(chunk)
            viseme = "aa" if jaw > 0.6 else ("E" if jaw > 0.3 else "sil")
        pcm_b64 = base64.b64encode(chunk).decode("ascii")
        await bus.publish(
            STREAM_TTS_AUDIO_CHUNK,
            TtsAudioChunk(
                source="voice",
                session_id=session_id,
                pcm_b64=pcm_b64,
                seq=seq,
                is_final=False,
                viseme=viseme,
            ),
        )
        # Multi-room : duplique vers l'enceinte sélectionnée (pas browser_main)
        try:
            target = speaker_router.select()
            if target is not None:
                sid, sp = target
                if sp.get("kind") not in (None, "browser"):
                    await push_to_speaker(sp, pcm_b64, viseme)
        except Exception as e:
            log.debug("multiroom push failed: %s", e)
        seq += 1
    if is_final or barge.is_set():
        await bus.publish(
            STREAM_TTS_AUDIO_CHUNK,
            TtsAudioChunk(
                source="voice",
                session_id=session_id,
                pcm_b64="",
                seq=seq,
                is_final=True,
                viseme="sil",
            ),
        )
        if barge.is_set():
            barge.clear()
    return seq + 1


async def tts_loop_full(bus: EventBus) -> None:
    """Consomme les réponses non-streamées (intent.response.ready)."""
    tts = make_tts()
    async for _id, ev in bus.consume(
        STREAM_INTENT_RESPONSE, "voice-tts", "voice-tts-1", IntentResponse
    ):
        try:
            log.info("tts session=%s text=%s", ev.session_id, ev.text[:80])
            await _tts_one(bus, tts, ev.session_id, ev.text, is_final=True, base_seq=0)
        except Exception as e:
            log.exception("TTS loop error: %s", e)


async def tts_loop_partial(bus: EventBus) -> None:
    """Consomme les phrases streamées (intent.response.partial)."""
    tts = make_tts()
    seq_by_session: dict[str, int] = defaultdict(int)
    async for _id, ev in bus.consume(
        STREAM_INTENT_RESPONSE_PARTIAL,
        "voice-tts-partial",
        "voice-tts-partial-1",
        IntentResponsePartial,
    ):
        try:
            base = seq_by_session[ev.session_id]
            seq_by_session[ev.session_id] = await _tts_one(
                bus, tts, ev.session_id, ev.text, is_final=ev.is_final, base_seq=base
            )
            if ev.is_final:
                seq_by_session.pop(ev.session_id, None)
        except Exception as e:
            log.exception("TTS partial loop error: %s", e)


async def barge_in_loop(bus: EventBus) -> None:
    async for _id, ev in bus.consume(
        STREAM_VOICE_BARGE_IN, "voice-bargein", "voice-bargein-1", VoiceBargeIn
    ):
        log.info("barge-in reçu session=%s", ev.session_id)
        _barge_event(ev.session_id).set()


async def main() -> None:
    bus = EventBus()
    await bus.connect()
    log.info("voice service ready")
    await asyncio.gather(
        stt_loop(bus),
        tts_loop_full(bus),
        tts_loop_partial(bus),
        barge_in_loop(bus),
    )


if __name__ == "__main__":
    asyncio.run(main())
