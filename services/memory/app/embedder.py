"""Embeddings via SentenceTransformers (bge-m3 par défaut, multilingue)."""

from __future__ import annotations

import logging
import os

log = logging.getLogger("memory.embed")


class Embedder:
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
        log.info("loading embedder %s", model_name)
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True)
        return vecs.tolist()
