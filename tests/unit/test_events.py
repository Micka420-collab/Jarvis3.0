"""Vérifie les schémas Pydantic du bus partagé."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))

from _shared.events import (
    ArgusAlert,
    IntentResponse,
    VoiceIdentityVerified,
    VoiceTranscriptReady,
)


def test_voice_transcript_defaults() -> None:
    ev = VoiceTranscriptReady(session_id="abc", text="bonjour")
    assert ev.lang == "fr"
    assert ev.confidence == 0.0
    assert ev.event_id


def test_intent_response_emotion_validation() -> None:
    ev = IntentResponse(session_id="s", text="ok", emotion="alert")
    assert ev.emotion == "alert"


def test_argus_alert_severity_constraint() -> None:
    ev = ArgusAlert(severity="critical", rule="r", host="h", summary="s")
    assert ev.severity == "critical"


def test_voice_identity_optional_user() -> None:
    ev = VoiceIdentityVerified(session_id="s", user_id=None, similarity=0.4, is_owner=False)
    assert ev.user_id is None
    assert ev.is_owner is False
