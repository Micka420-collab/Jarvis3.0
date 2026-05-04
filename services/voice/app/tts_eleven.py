"""TTS via ElevenLabs (cloud, voix premium)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator

import httpx

from .providers import TTSProvider

log = logging.getLogger("voice.tts.eleven")


class ElevenLabsTTS(TTSProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        if not self.api_key or not self.voice_id:
            raise RuntimeError("ELEVENLABS_API_KEY et ELEVENLABS_VOICE_ID requis")

    async def synthesize_stream(self, text: str) -> AsyncIterator[tuple[bytes, str | None]]:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "output_format": "pcm_22050",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk, None
