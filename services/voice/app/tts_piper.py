"""TTS via Piper (rapide, CPU, voix fr)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from .providers import TTSProvider

log = logging.getLogger("voice.tts.piper")


class PiperTTS(TTSProvider):
    def __init__(self) -> None:
        from piper import PiperVoice  # import retardé

        voice_name = os.getenv("PIPER_VOICE", "fr_FR-siwis-medium")
        models_dir = Path("/models/piper")
        model_path = models_dir / f"{voice_name}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modèle Piper introuvable: {model_path}. Exécute `make download-models`."
            )
        log.info("loading piper voice=%s", voice_name)
        self.voice = PiperVoice.load(str(model_path))

    async def synthesize_stream(self, text: str) -> AsyncIterator[tuple[bytes, str | None]]:
        # Piper synthesize renvoie des chunks raw int16
        for audio_bytes in self.voice.synthesize_stream_raw(text):
            # TODO: extraire les phonèmes pour piloter les visèmes
            yield audio_bytes, None
