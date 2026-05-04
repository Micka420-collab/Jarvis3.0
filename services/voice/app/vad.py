"""Voice Activity Detection (silero-vad).

Segmente un flux PCM 16-bit mono 16 kHz en utterances en détectant
le début et la fin de la parole.
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger("voice.vad")

# Paramètres tirés des recommandations silero
FRAME_SAMPLES = 512  # 32 ms à 16 kHz
SPEECH_THRESHOLD = 0.5
MIN_SILENCE_FRAMES = 25  # ~800 ms de silence pour fin d'utterance
MIN_SPEECH_FRAMES = 6   # ~200 ms de parole pour valider un début


class VAD:
    def __init__(self) -> None:
        import torch

        torch.set_num_threads(1)
        try:
            from silero_vad import load_silero_vad

            self.model = load_silero_vad()
        except Exception:
            # fallback API ancienne
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True
            )
            self.model = model

    def reset(self) -> None:
        if hasattr(self.model, "reset_states"):
            self.model.reset_states()


class StreamSegmenter:
    """Reçoit des chunks PCM et émet des utterances complètes."""

    def __init__(self, vad: VAD) -> None:
        import torch

        self.torch = torch
        self.vad = vad
        self._buffer = bytearray()
        self._frame_buffer = bytearray()
        self._speech_run = 0
        self._silence_run = 0
        self._in_speech = False
        self._utterance = bytearray()

    def push(self, pcm16: bytes) -> list[bytes]:
        """Retourne 0..N utterances détectées dans ce chunk."""
        utterances: list[bytes] = []
        self._frame_buffer.extend(pcm16)
        # consomme par frames de 512 échantillons (1024 octets)
        frame_bytes = FRAME_SAMPLES * 2
        while len(self._frame_buffer) >= frame_bytes:
            frame = bytes(self._frame_buffer[:frame_bytes])
            del self._frame_buffer[:frame_bytes]
            audio = (
                self.torch.from_numpy(np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0)
            )
            prob = float(self.vad.model(audio, 16_000).item())
            is_speech = prob >= SPEECH_THRESHOLD
            if is_speech:
                self._speech_run += 1
                self._silence_run = 0
                if not self._in_speech and self._speech_run >= MIN_SPEECH_FRAMES:
                    self._in_speech = True
                if self._in_speech:
                    self._utterance.extend(frame)
            else:
                self._silence_run += 1
                if self._in_speech:
                    self._utterance.extend(frame)
                    if self._silence_run >= MIN_SILENCE_FRAMES:
                        utterances.append(bytes(self._utterance))
                        self._utterance.clear()
                        self._in_speech = False
                        self._speech_run = 0
                else:
                    self._speech_run = max(self._speech_run - 1, 0)
        return utterances

    def flush(self) -> bytes | None:
        """Force la fin d'utterance (sur "end" du client)."""
        if self._in_speech and self._utterance:
            out = bytes(self._utterance)
            self._utterance.clear()
            self._in_speech = False
            self._speech_run = 0
            return out
        return None
