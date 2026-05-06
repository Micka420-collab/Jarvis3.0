"""Interfaces ABC pour STT et TTS — implémentations swappables."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, pcm16: bytes, sample_rate: int = 16_000) -> tuple[str, float]:
        """Retourne (texte, confiance). pcm16 = mono PCM 16-bit."""


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncIterator[tuple[bytes, str | None]]:
        """Stream PCM 16-bit mono 22050 Hz, par chunks (pcm, viseme_optionnel)."""
