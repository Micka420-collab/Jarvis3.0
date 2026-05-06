"""Détection anti-spoofing/deepfake avec AASIST.

AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph
Attention Networks) est un modèle SOTA de la challenge ASVspoof 2021.

Modèle ONNX : tu peux récupérer un export depuis https://huggingface.co/cuongdang/aasist-onnx
ou réexporter depuis le repo officiel https://github.com/clovaai/aasist.

Le fichier doit être placé dans /models/aasist/aasist.onnx dans le conteneur voice.
Si absent, le checker reste désactivé (les commandes admin restent gatées
par la voix-print + challenge phrase).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("voice.liveness")

DEFAULT_MODEL = Path("/models/aasist/aasist.onnx")
DEFAULT_THRESHOLD = float(os.getenv("LIVENESS_THRESHOLD", "0.5"))
TARGET_SR = 16_000
TARGET_LEN = 64_600  # ~4s comme dans le papier AASIST


@dataclass
class LivenessResult:
    score: float          # ∈ [0,1], plus haut = plus humain
    is_human: bool
    threshold: float


class LivenessChecker:
    def __init__(self, model_path: Path | None = None, threshold: float = DEFAULT_THRESHOLD) -> None:
        path = Path(model_path or os.getenv("AASIST_MODEL_PATH", DEFAULT_MODEL))
        if not path.exists():
            raise FileNotFoundError(
                f"Modèle AASIST introuvable: {path}. "
                "Télécharge un export ONNX et place-le dans /models/aasist/aasist.onnx"
            )
        import onnxruntime as ort

        self.threshold = threshold
        self.session = ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"],
        )
        # nom de l'entrée : varie selon l'export (souvent "input" ou "audio")
        self.input_name = self.session.get_inputs()[0].name
        log.info("AASIST liveness chargé: %s (input=%s)", path, self.input_name)

    @staticmethod
    def _prepare(pcm16: bytes) -> np.ndarray:
        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        # padding ou crop à TARGET_LEN
        if len(audio) >= TARGET_LEN:
            audio = audio[:TARGET_LEN]
        else:
            reps = TARGET_LEN // max(1, len(audio)) + 1
            audio = np.tile(audio, reps)[:TARGET_LEN]
        return audio.reshape(1, -1)  # batch=1

    def score(self, pcm16: bytes, sample_rate: int = TARGET_SR) -> LivenessResult:
        if sample_rate != TARGET_SR:
            log.warning("AASIST attend %d Hz, reçu %d Hz", TARGET_SR, sample_rate)
        x = self._prepare(pcm16)
        out = self.session.run(None, {self.input_name: x})
        # AASIST renvoie typiquement [bonafide_logit, spoof_logit]
        logits = np.array(out[0]).reshape(-1)
        if logits.shape[0] >= 2:
            # softmax sur les deux classes
            ex = np.exp(logits - np.max(logits))
            probs = ex / ex.sum()
            # convention: classe 0 = bonafide (humain)
            human_prob = float(probs[0])
        else:
            # exports avec score scalaire dans [0,1]
            human_prob = float(1.0 / (1.0 + np.exp(-logits[0])))
        return LivenessResult(
            score=human_prob,
            is_human=human_prob >= self.threshold,
            threshold=self.threshold,
        )
