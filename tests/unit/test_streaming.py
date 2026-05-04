"""Tests du sentence chunker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))

from app.streaming import split_text_into_sentences


def test_simple_sentences() -> None:
    out = list(split_text_into_sentences("Bonjour. Comment ça va ? Bien sûr !"))
    assert out == ["Bonjour.", "Comment ça va ?", "Bien sûr !"]


def test_no_break_on_abbreviation() -> None:
    out = list(split_text_into_sentences("Bonjour M. Dupont. Comment allez-vous ?"))
    # On ne casse pas après "M." → la 1ère phrase reste collée à "Dupont."
    assert out[0].startswith("Bonjour M. Dupont")


def test_trailing_fragment_is_emitted() -> None:
    out = list(split_text_into_sentences("OK. fin sans ponctuation"))
    assert out == ["OK.", "fin sans ponctuation"]


def test_ellipsis() -> None:
    out = list(split_text_into_sentences("Hum… vraiment ?"))
    assert out == ["Hum…", "vraiment ?"]
