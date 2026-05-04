"""Schémas Pydantic des événements Redis Streams partagés entre services.

Convention de nommage des streams : `<domaine>.<sujet>.<verbe>`
Tous les événements héritent de `BaseEvent` (id, ts, source).
"""

from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------

STREAM_VOICE_AUDIO_CHUNK = "voice.audio.chunk"
STREAM_VOICE_UTTERANCE = "voice.utterance.detected"
STREAM_VOICE_TRANSCRIPT = "voice.transcript.ready"
STREAM_VOICE_IDENTITY = "voice.identity.verified"
STREAM_INTENT_REQUEST = "intent.command.requested"
STREAM_INTENT_RESPONSE = "intent.response.ready"
STREAM_TTS_AUDIO_CHUNK = "tts.audio.chunk"
STREAM_IOT_COMMAND = "iot.device.commanded"
STREAM_IOT_STATE = "iot.device.state"
STREAM_ARGUS_ALERT = "argus.alert.received"
STREAM_MEMORY_FACT = "memory.fact.stored"
STREAM_VISION_FACE = "vision.face.recognized"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    return int(time.time() * 1000)


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts_ms: int = Field(default_factory=_now_ms)
    source: str = "unknown"


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


class VoiceAudioChunk(BaseEvent):
    session_id: str
    pcm_b64: str  # PCM 16-bit mono 16 kHz, base64
    seq: int


class VoiceUtteranceDetected(BaseEvent):
    session_id: str
    audio_ref: str  # clé MinIO ou chemin temporaire
    duration_ms: int


class VoiceTranscriptReady(BaseEvent):
    session_id: str
    text: str
    lang: str = "fr"
    confidence: float = 0.0


class VoiceIdentityVerified(BaseEvent):
    session_id: str
    user_id: str | None  # None = inconnu
    similarity: float
    is_owner: bool
    challenge_passed: bool | None = None


# ---------------------------------------------------------------------------
# Intents (orchestrator)
# ---------------------------------------------------------------------------


class IntentRequest(BaseEvent):
    session_id: str
    user_id: str | None
    intent: str
    slots: dict[str, str | int | float | bool] = {}
    requires_admin: bool = False
    raw_text: str = ""


class IntentResponse(BaseEvent):
    session_id: str
    text: str
    emotion: Literal["neutral", "happy", "concerned", "alert"] = "neutral"
    proactive: bool = False  # poussé sans demande utilisateur


# ---------------------------------------------------------------------------
# TTS streaming
# ---------------------------------------------------------------------------


class TtsAudioChunk(BaseEvent):
    session_id: str
    pcm_b64: str
    seq: int
    is_final: bool = False
    viseme: str | None = None  # phonème courant pour lipsync


# ---------------------------------------------------------------------------
# IoT
# ---------------------------------------------------------------------------


class IotDeviceCommand(BaseEvent):
    device_id: str
    action: str
    params: dict[str, str | int | float | bool] = {}
    transport: Literal["mqtt", "homeassistant", "serial"] = "mqtt"


class IotDeviceState(BaseEvent):
    device_id: str
    state: dict[str, str | int | float | bool]
    transport: Literal["mqtt", "homeassistant", "serial"] = "mqtt"


# ---------------------------------------------------------------------------
# Sécurité (Argus)
# ---------------------------------------------------------------------------


class ArgusAlert(BaseEvent):
    severity: Literal["info", "low", "medium", "high", "critical"]
    rule: str
    host: str
    summary: str
    raw: dict = {}


# ---------------------------------------------------------------------------
# Mémoire
# ---------------------------------------------------------------------------


class MemoryFact(BaseEvent):
    fact_id: str
    user_id: str | None
    text: str
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------


class VisionFaceRecognized(BaseEvent):
    camera: str
    name: str | None  # None = visage inconnu
    confidence: float
    bbox: tuple[int, int, int, int] | None = None
