"""Scoring composite pour le recall mémoire.

Plutôt que renvoyer le top-K par similarité brute, on combine 4 signaux :

  final_score = w_sim * similarity
              + w_rec * recency_decay
              + w_imp * importance
              + w_use * use_signal

  similarity     : score Qdrant (0..1, cosinus normalisé)
  recency_decay  : exp(-age_days / half_life_days), half_life par défaut 90 j
  importance     : valeur stockée 0..1
  use_signal     : log(1 + recall_count) / log(1 + max_recalls) borné

Poids ajustables via env vars (MEM_W_SIM, MEM_W_REC, MEM_W_IMP, MEM_W_USE).
La somme des poids doit donner ~1.0 pour rester interprétable.
"""

from __future__ import annotations

import datetime as dt
import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringWeights:
    sim: float = float(os.getenv("MEM_W_SIM", "0.55"))
    recency: float = float(os.getenv("MEM_W_REC", "0.20"))
    importance: float = float(os.getenv("MEM_W_IMP", "0.15"))
    use: float = float(os.getenv("MEM_W_USE", "0.10"))
    half_life_days: float = float(os.getenv("MEM_HALF_LIFE_DAYS", "90"))
    max_recalls: int = int(os.getenv("MEM_MAX_RECALLS", "20"))


def recency_decay(created_at: dt.datetime, *, now: dt.datetime | None = None,
                  half_life_days: float = 90.0) -> float:
    """Decay exponentiel sur l'âge. À l'heure 0 → 1.0, après half_life → 0.5."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=dt.timezone.utc)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return math.exp(-age_days * math.log(2) / max(0.1, half_life_days))


def use_score(recall_count: int, max_recalls: int = 20) -> float:
    """Plus on rappelle un fait, plus il monte (saturation log)."""
    if recall_count <= 0:
        return 0.0
    return min(1.0, math.log1p(recall_count) / math.log1p(max(1, max_recalls)))


def composite_score(
    *,
    similarity: float,
    created_at: dt.datetime,
    importance: float = 0.5,
    recall_count: int = 0,
    weights: ScoringWeights | None = None,
    now: dt.datetime | None = None,
) -> float:
    """Combine 4 signaux. Tous bornés [0,1] → résultat [0,1]."""
    w = weights or ScoringWeights()
    sim = max(0.0, min(1.0, similarity))
    rec = recency_decay(created_at, now=now, half_life_days=w.half_life_days)
    imp = max(0.0, min(1.0, importance))
    use = use_score(recall_count, max_recalls=w.max_recalls)
    return w.sim * sim + w.recency * rec + w.importance * imp + w.use * use


def reciprocal_rank_fusion(
    rankings: list[list[str]], *, k: int = 60
) -> list[tuple[str, float]]:
    """RRF : combine plusieurs classements (vector + BM25 + …) sans normalisation.

    Pour chaque liste, l'élément à la position i contribue 1/(k+i) au score
    cumulé de son ID. Référence : Cormack 2009, k=60 = bon défaut empirique.
    """
    cumul: dict[str, float] = {}
    for ranking in rankings:
        for idx, item_id in enumerate(ranking):
            cumul[item_id] = cumul.get(item_id, 0.0) + 1.0 / (k + idx + 1)
    return sorted(cumul.items(), key=lambda kv: -kv[1])
