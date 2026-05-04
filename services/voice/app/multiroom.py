"""Multi-room audio : route le TTS vers l'enceinte la plus pertinente.

Stratégie :
1. Détermine la pièce d'occupation la plus récente (table observations + events
   `vision.face.recognized` channel ui.vision).
2. Cherche une enceinte associée à cette pièce (registre `speakers.yaml`).
3. Si l'enceinte est occupée par un autre média (état `playing`), choisit la
   pièce libre la plus proche (ordre défini dans le registre).
4. Pousse le TTS sur l'enceinte sélectionnée :
   - Snapcast / Squeezelite : URL stream HTTP
   - MQTT topic dédié `jarvis/speakers/<room>/play` (payload base64 wav)
   - Default : envoyer vers le browser local (fallback)
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml

log = logging.getLogger("voice.multiroom")

SPEAKERS_FILE = Path(__file__).parent / "speakers.yaml"


SpeakerKind = Literal["browser", "mqtt", "snapcast", "squeezelite", "homeassistant"]


def load_speakers() -> dict[str, dict]:
    if not SPEAKERS_FILE.exists():
        return {}
    raw = yaml.safe_load(SPEAKERS_FILE.read_text(encoding="utf-8")) or {}
    return {s["id"]: s for s in raw.get("speakers", [])}


class SpeakerRouter:
    def __init__(self) -> None:
        self.speakers = load_speakers()
        # état : pièce → timestamp de dernière présence
        self._presence_ts: dict[str, float] = {}
        # état : speaker → "idle" | "busy"
        self._busy: dict[str, bool] = {s: False for s in self.speakers}

    def update_presence(self, room: str, ts: float) -> None:
        self._presence_ts[room] = ts

    def mark_speaker(self, speaker_id: str, busy: bool) -> None:
        self._busy[speaker_id] = busy

    def select(self, fallback: str = "browser") -> tuple[str, dict] | None:
        """Choisit l'enceinte cible : pièce occupée la plus récente + libre."""
        if not self.speakers:
            return None
        # tri pièces par fraîcheur de présence
        rooms_sorted = sorted(self._presence_ts.items(), key=lambda kv: -kv[1])
        for room, _ts in rooms_sorted:
            for sid, sp in self.speakers.items():
                if sp.get("room") == room and not self._busy.get(sid, False):
                    return sid, sp
        # personne détecté → fallback (la 1ère enceinte libre, ou enceinte du salon)
        for sid, sp in self.speakers.items():
            if sp.get("default") and not self._busy.get(sid, False):
                return sid, sp
        for sid, sp in self.speakers.items():
            if not self._busy.get(sid, False):
                return sid, sp
        return None

    def list_iter(self) -> Iterable[tuple[str, dict]]:
        return self.speakers.items()


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


async def push_to_speaker(speaker: dict, pcm_b64: str, viseme: str | None = None) -> None:
    """Pousse un chunk TTS vers le backend approprié."""
    kind = speaker.get("kind", "browser")
    if kind == "browser":
        return  # rien à faire : le gateway streame déjà sur la WS browser
    if kind == "mqtt":
        from .._mqtt import publish_async

        topic = speaker["topic"]
        await publish_async(topic, {"pcm_b64": pcm_b64, "viseme": viseme})
        return
    if kind == "snapcast":
        # snapcast : on POST le PCM brut sur /streams/<id>
        import httpx

        url = speaker["url"]
        async with httpx.AsyncClient(timeout=2.0) as c:
            await c.post(url, data=pcm_b64)
        return
    if kind == "homeassistant":
        # service media_player.play_media avec un blob base64 (HA TTS proxy nécessaire)
        import httpx

        ha_url = os.getenv("HA_BASE_URL", "http://homeassistant:8123")
        token = os.getenv("HA_LONG_LIVED_TOKEN", "")
        async with httpx.AsyncClient(timeout=3.0) as c:
            await c.post(
                f"{ha_url}/api/services/media_player/play_media",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "entity_id": speaker["entity_id"],
                    "media_content_type": "audio/wav",
                    "media_content_id": f"data:audio/wav;base64,{pcm_b64}",
                },
            )
        return
    log.warning("speaker kind inconnu: %s", kind)
