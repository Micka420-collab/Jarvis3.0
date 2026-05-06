"""Voix-print : ECAPA-TDNN (SpeechBrain) pour vérifier l'identité du créateur.

- Enrôlement : `scripts/enroll_voiceprint.py` (5 phrases, ~30 s)
- Vérification : cosine similarity vs embedding owner stocké en pgvector
- Anti-replay : challenge phrase dynamique côté orchestrator
"""

from __future__ import annotations

import logging
import os

import numpy as np

log = logging.getLogger("voice.voiceprint")

ECAPA_DIM = 192


class VoiceprintEngine:
    def __init__(self) -> None:
        from speechbrain.inference.speaker import EncoderClassifier

        models_dir = os.getenv("ECAPA_MODEL_DIR", "/models/ecapa")
        log.info("loading ECAPA-TDNN from %s", models_dir)
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=models_dir,
            run_opts={"device": "cpu"},
        )

    def embed(self, pcm16: bytes, sample_rate: int = 16_000) -> np.ndarray:
        import torch

        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        wav = torch.from_numpy(audio).unsqueeze(0)
        emb = self.encoder.encode_batch(wav).squeeze().detach().cpu().numpy()
        # L2-normalisation
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        assert emb.shape[-1] == ECAPA_DIM, f"shape inattendue: {emb.shape}"
        return emb

    @staticmethod
    def similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))  # déjà L2-normalisés → cosine
