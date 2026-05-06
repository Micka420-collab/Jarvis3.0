"""Wake-word detection (openWakeWord). Optionnel : si la VAD prend le relais
on peut désactiver le wake-word via ENV WAKE_WORD=disabled.
"""

from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger("voice.wake")


class WakeWordDetector:
    def __init__(self) -> None:
        self.enabled = os.getenv("WAKE_WORD", "jarvis").lower() != "disabled"
        self.threshold = float(os.getenv("WAKE_WORD_THRESHOLD", "0.6"))
        self.model = None
        if self.enabled:
            try:
                from openwakeword.model import Model

                self.model = Model(wakeword_models=["jarvis"])
                log.info("wake-word activé (jarvis), seuil=%s", self.threshold)
            except Exception as e:
                log.warning("wake-word KO (%s) — fallback sur VAD seul", e)
                self.enabled = False

    def detect(self, pcm16: bytes) -> bool:
        if not self.enabled or self.model is None:
            return True  # toujours actif si désactivé
        audio = np.frombuffer(pcm16, dtype=np.int16)
        scores = self.model.predict(audio)
        return any(s >= self.threshold for s in scores.values())
