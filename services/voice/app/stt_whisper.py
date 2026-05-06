"""STT via faster-whisper (CTranslate2)."""

from __future__ import annotations

import logging
import os
from io import BytesIO

import numpy as np
import soundfile as sf

from .providers import STTProvider

log = logging.getLogger("voice.stt")


class WhisperSTT(STTProvider):
    def __init__(self) -> None:
        from faster_whisper import WhisperModel  # import retardé pour démarrage léger

        model_name = os.getenv("WHISPER_MODEL", "small")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        log.info("loading whisper model=%s device=%s ctype=%s", model_name, device, compute_type)
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.lang = os.getenv("WHISPER_LANG", "fr")

    async def transcribe(self, pcm16: bytes, sample_rate: int = 16_000) -> tuple[str, float]:
        if not pcm16:
            return "", 0.0
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        # faster-whisper attend du float32 mono ou un fichier ; on lui passe le ndarray.
        segments, info = self.model.transcribe(
            audio,
            language=self.lang,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts: list[str] = []
        avg_logprob_sum = 0.0
        n = 0
        for seg in segments:
            parts.append(seg.text.strip())
            avg_logprob_sum += seg.avg_logprob
            n += 1
        text = " ".join(parts).strip()
        confidence = float(np.exp(avg_logprob_sum / n)) if n else 0.0
        return text, confidence
