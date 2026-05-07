"""Embeddings via SentenceTransformers (bge-m3 par défaut, multilingue).

Améliorations vs version initiale :
- Cache LRU sur l'encoding des queries (les mêmes questions reviennent souvent)
- Lazy-load du modèle pour démarrer plus vite
- Encoding batch optimisé via le model.encode() de sentence-transformers
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict

log = logging.getLogger("memory.embed")


class _LRUCache:
    """Cache simple thread-safe-ish (1 process FastAPI, asyncio mono-thread)."""

    def __init__(self, max_items: int = 256) -> None:
        self.max_items = max_items
        self._d: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def put(self, key: str, value: list[float]) -> None:
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        while len(self._d) > self.max_items:
            self._d.popitem(last=False)

    def __len__(self) -> int:
        return len(self._d)


class Embedder:
    def __init__(self) -> None:
        self.model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
        self._model = None
        self._dim_cache: int | None = None
        self.cache = _LRUCache(max_items=int(os.getenv("EMBED_CACHE_SIZE", "256")))

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("loading embedder %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self._dim_cache = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dim(self) -> int:
        if self._dim_cache is None:
            self._ensure_model()
        return self._dim_cache  # type: ignore[return-value]

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()

    def encode(self, texts: list[str], *, use_cache: bool = True) -> list[list[float]]:
        """Encode une liste. Pour chaque texte présent dans le cache, on saute
        l'encoding ; sinon on batch ensemble pour un seul appel modèle.
        """
        if not texts:
            return []
        if not use_cache:
            return self._encode_raw(texts)
        out: list[list[float] | None] = [None] * len(texts)
        to_encode: list[tuple[int, str]] = []
        for i, t in enumerate(texts):
            cached = self.cache.get(self._hash(t))
            if cached is not None:
                out[i] = cached
            else:
                to_encode.append((i, t))
        if to_encode:
            vecs = self._encode_raw([t for _, t in to_encode])
            for (idx, _), v in zip(to_encode, vecs):
                out[idx] = v
                self.cache.put(self._hash(texts[idx]), v)
        return out  # type: ignore[return-value]

    def _encode_raw(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vecs.tolist()
