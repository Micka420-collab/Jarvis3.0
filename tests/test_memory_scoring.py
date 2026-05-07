"""Tests scoring composite + RRF."""

from __future__ import annotations

import datetime as dt

from scoring import (
    ScoringWeights,
    composite_score,
    reciprocal_rank_fusion,
    recency_decay,
    use_score,
)


def test_recency_decay_fresh():
    """Un fact créé il y a quelques secondes → score ≈ 1.0"""
    now = dt.datetime.now(dt.timezone.utc)
    assert recency_decay(now, now=now, half_life_days=90) > 0.99


def test_recency_decay_half_life():
    """Au half_life, decay = 0.5"""
    now = dt.datetime.now(dt.timezone.utc)
    half_life = 90
    created = now - dt.timedelta(days=half_life)
    assert abs(recency_decay(created, now=now, half_life_days=half_life) - 0.5) < 0.01


def test_recency_decay_old():
    """Très ancien → score proche de 0"""
    now = dt.datetime.now(dt.timezone.utc)
    created = now - dt.timedelta(days=365 * 5)
    assert recency_decay(created, now=now, half_life_days=90) < 0.05


def test_use_score_zero():
    assert use_score(0) == 0.0


def test_use_score_monotonic():
    """Plus on rappelle, plus le score monte (saturation log)."""
    s = [use_score(n) for n in [1, 5, 10, 20]]
    assert s == sorted(s)
    assert all(0 < x <= 1 for x in s)


def test_use_score_saturates():
    assert use_score(20, max_recalls=20) == 1.0
    assert use_score(1000, max_recalls=20) == 1.0


def test_composite_score_in_range():
    now = dt.datetime.now(dt.timezone.utc)
    s = composite_score(
        similarity=0.9, created_at=now, importance=0.5, recall_count=2,
    )
    assert 0.0 <= s <= 1.0


def test_composite_score_recent_beats_old():
    """Avec mêmes similarity/importance/use, le plus récent doit gagner."""
    now = dt.datetime.now(dt.timezone.utc)
    fresh = composite_score(similarity=0.7, created_at=now, importance=0.5)
    stale = composite_score(
        similarity=0.7, created_at=now - dt.timedelta(days=400), importance=0.5,
    )
    assert fresh > stale


def test_composite_score_high_similarity_dominates():
    now = dt.datetime.now(dt.timezone.utc)
    high = composite_score(similarity=0.95, created_at=now, importance=0.0)
    low = composite_score(similarity=0.10, created_at=now, importance=1.0)
    # similarity poids 0.55, importance 0.15 → similarity gagne en moyenne
    assert high > low


def test_weights_sum_default():
    w = ScoringWeights()
    total = w.sim + w.recency + w.importance + w.use
    assert abs(total - 1.0) < 0.01, f"weights sum != 1.0 ({total})"


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_single_ranking():
    out = reciprocal_rank_fusion([["a", "b", "c"]])
    ids = [k for k, _ in out]
    assert ids == ["a", "b", "c"]


def test_rrf_combines_two_rankings():
    """Un item présent dans les 2 listes doit remonter au-dessus d'un seul."""
    out = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d", "e"]])
    ids_top3 = [k for k, _ in out[:3]]
    assert "b" in ids_top3
    # 'b' est en pos 2 dans liste 1 et pos 1 dans liste 2 → meilleur que 'a' (pos 1 + absent)
    assert ids_top3.index("b") < ids_top3.index("a")
