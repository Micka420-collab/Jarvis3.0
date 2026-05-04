"""Reconnaissance faciale via InsightFace (buffalo_l)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger("vision.face")

KNOWN_DIR = Path(os.getenv("KNOWN_FACES_DIR", "/models/known_faces"))
THRESHOLD = float(os.getenv("FACE_THRESHOLD", "0.45"))


class FaceRecognizer:
    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        self.app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        self.known: dict[str, np.ndarray] = {}
        self._load_known()

    def _load_known(self) -> None:
        if not KNOWN_DIR.exists():
            log.info("KNOWN_FACES_DIR vide (%s)", KNOWN_DIR)
            return
        import cv2

        for img_path in KNOWN_DIR.glob("*.jpg"):
            name = img_path.stem
            img = cv2.imread(str(img_path))
            faces = self.app.get(img)
            if faces:
                emb = faces[0].normed_embedding
                self.known[name] = emb
                log.info("face enrolled: %s", name)

    def identify(self, img_bgr: np.ndarray) -> list[tuple[str | None, float, tuple[int, int, int, int]]]:
        faces = self.app.get(img_bgr)
        out = []
        for f in faces:
            best_name, best_sim = None, 0.0
            for name, ref in self.known.items():
                sim = float(np.dot(f.normed_embedding, ref))
                if sim > best_sim:
                    best_sim, best_name = sim, name
            if best_sim < THRESHOLD:
                best_name = None
            x1, y1, x2, y2 = map(int, f.bbox)
            out.append((best_name, best_sim, (x1, y1, x2, y2)))
        return out
