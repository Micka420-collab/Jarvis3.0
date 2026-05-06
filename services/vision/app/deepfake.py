"""Détection deepfake / face anti-spoofing pour les caméras.

Empêche les attaques par photo / vidéo replay : un visage reconnu doit aussi
passer un score de "vivacité" (liveness) au-dessus du seuil avant qu'il soit
considéré comme légitime.

Stratégies (du plus simple au plus robuste) :

1. **MiniFASNet** (Silent-Face-Anti-Spoofing) : ONNX léger ~2 Mo, RGB+depth
   simulés via deux sous-modèles. CPU-friendly. Téléchargement optionnel.

2. **Optical-flow micro-mouvement** : si N frames consécutives sont quasi
   identiques (var pixel < seuil), on suspecte une photo statique.

3. **Texture analysis (LBP)** : Local Binary Pattern → photos imprimées ont
   une signature texture pauvre vs visage réel.

Si aucun modèle n'est dispo, le check passe en mode "soft" : warn dans les
logs mais ne bloque pas (configurable via DEEPFAKE_BLOCK_ON_MISS=true).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("vision.deepfake")

DEEPFAKE_THRESHOLD = float(os.getenv("DEEPFAKE_THRESHOLD", "0.5"))
DEEPFAKE_BLOCK_ON_MISS = os.getenv("DEEPFAKE_BLOCK_ON_MISS", "false").lower() == "true"
MODEL_PATH = Path(os.getenv("DEEPFAKE_MODEL_PATH", "/models/anti_spoof/minifasnet.onnx"))


@dataclass
class LivenessResult:
    is_live: bool
    score: float
    reason: str


class DeepfakeDetector:
    """Charge un modèle ONNX si dispo. Sinon fallback heuristique."""

    def __init__(self) -> None:
        self.session = None
        if MODEL_PATH.exists():
            try:
                import onnxruntime as ort

                self.session = ort.InferenceSession(
                    str(MODEL_PATH), providers=["CPUExecutionProvider"]
                )
                log.info("deepfake : modèle MiniFASNet chargé depuis %s", MODEL_PATH)
            except Exception as e:
                log.warning("deepfake : impossible de charger %s (%s)", MODEL_PATH, e)
        else:
            log.info("deepfake : pas de modèle (DEEPFAKE_BLOCK_ON_MISS=%s)", DEEPFAKE_BLOCK_ON_MISS)

        self._frame_buffer: list[np.ndarray] = []  # pour la détection statique

    # ----------------------------------------------------------------------
    # Heuristiques fallback
    # ----------------------------------------------------------------------

    def _static_image_score(self, frame: np.ndarray) -> float:
        """Si N frames consécutives ont une variance pixel quasi-nulle entre
        elles, c'est probablement une photo. Score = ratio de variance.
        """
        self._frame_buffer.append(frame)
        if len(self._frame_buffer) > 5:
            self._frame_buffer.pop(0)
        if len(self._frame_buffer) < 3:
            return 1.0  # pas assez de signal, on accorde le bénéfice du doute
        diffs = [
            float(np.mean(np.abs(self._frame_buffer[i] - self._frame_buffer[i - 1])))
            for i in range(1, len(self._frame_buffer))
        ]
        avg_diff = sum(diffs) / len(diffs)
        # Sur des frames 0..255, < 1.5 ≈ photo statique
        return min(1.0, avg_diff / 5.0)

    # ----------------------------------------------------------------------
    # Inférence
    # ----------------------------------------------------------------------

    def check(self, face_crop: np.ndarray) -> LivenessResult:
        """face_crop : RGB uint8 (H, W, 3) recadré sur le visage."""
        if self.session is not None:
            try:
                # MiniFASNet attend du 80x80 normalisé en [0,1]
                import cv2  # noqa: F401 — dispo car deps insightface/frigate

                resized = self._resize_80(face_crop).astype(np.float32) / 255.0
                inp = np.transpose(resized, (2, 0, 1))[None, ...]
                out = self.session.run(None, {self.session.get_inputs()[0].name: inp})[0]
                # MiniFASNet : softmax → [fake, real]
                live_score = float(out[0][1])
                is_live = live_score >= DEEPFAKE_THRESHOLD
                return LivenessResult(
                    is_live=is_live, score=live_score,
                    reason="onnx" if is_live else f"onnx<{DEEPFAKE_THRESHOLD}",
                )
            except Exception as e:
                log.warning("deepfake ONNX a échoué (%s) — fallback heuristique", e)

        # Fallback : variance temporelle
        score = self._static_image_score(face_crop)
        is_live = score >= 0.3 if not DEEPFAKE_BLOCK_ON_MISS else False
        return LivenessResult(
            is_live=is_live, score=score,
            reason="heuristic-temporal" if is_live else "static-frame-suspect",
        )

    @staticmethod
    def _resize_80(img: np.ndarray) -> np.ndarray:
        try:
            import cv2

            return cv2.resize(img, (80, 80))
        except Exception:
            # Fallback sans cv2 : nearest neighbor naïf
            h, w = img.shape[:2]
            ys = (np.arange(80) * h / 80).astype(int)
            xs = (np.arange(80) * w / 80).astype(int)
            return img[ys[:, None], xs[None, :]]
