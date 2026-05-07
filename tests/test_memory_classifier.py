"""Tests du classifieur heuristique de catégorie + importance auto."""

from __future__ import annotations

import pytest

from classifier import auto_importance, classify


@pytest.mark.parametrize("text,expected", [
    ("J'aime le café noir le matin", "preference"),
    ("J'adore les films de Tarantino", "preference"),
    ("Je n'aime pas le bruit", "preference"),
    ("Je préfère le chocolat noir", "preference"),
    ("I love coffee in the morning", "preference"),
    ("Hier je suis allé au cinéma", "event"),
    ("La semaine dernière j'ai rencontré Marie", "event"),
    ("Yesterday I visited my parents", "event"),
    ("Je me lève toujours à 7h du matin", "skill_observation"),
    ("Chaque lundi je vais à la salle", "skill_observation"),
    ("J'habite à Lyon", "fact"),
    ("Je travaille chez Acme depuis 2020", "fact"),
    ("Marie m'a dit qu'elle viendrait", "conversation"),
    ("blablabla random text", "other"),
])
def test_classify(text, expected):
    assert classify(text) == expected


def test_classify_empty():
    assert classify("") == "other"
    assert classify("   ") == "other"


def test_auto_importance_in_range():
    for kind in ("preference", "fact", "event", "skill_observation", "conversation", "other"):
        imp = auto_importance("texte neutre", kind)
        assert 0.0 <= imp <= 1.0


def test_auto_importance_preference_higher_than_event():
    pref = auto_importance("J'aime le thé", "preference")
    evt = auto_importance("Hier j'ai mangé une pomme", "event")
    assert pref > evt


def test_auto_importance_boost_marker():
    """'Important' ou 'rappelle-toi' doit booster."""
    base = auto_importance("Je sors demain", "fact")
    boosted = auto_importance("IMPORTANT : rappelle-toi que je sors demain", "fact")
    assert boosted > base
    assert boosted <= 1.0


def test_auto_importance_boost_birthday():
    base = auto_importance("Marie aime le jaune", "fact")
    boost = auto_importance("L'anniversaire de Marie est le 5 mars", "fact")
    assert boost > base
