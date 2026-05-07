"""Tests du chunker."""

from __future__ import annotations

from chunker import chunk_text, split_sentences


def test_split_sentences_simple():
    out = split_sentences("Bonjour. Comment ça va ? Très bien !")
    assert out == ["Bonjour.", "Comment ça va ?", "Très bien !"]


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_chunk_short_text_passes_through():
    text = "C'est un texte court qui tient en un chunk."
    assert chunk_text(text, target_chars=600) == [text]


def test_chunk_empty():
    assert chunk_text("") == []


def test_chunk_long_text_produces_multiple_chunks():
    long = ". ".join(["Ceci est une phrase de test"] * 50)
    chunks = chunk_text(long, target_chars=200, overlap_chars=20)
    assert len(chunks) > 1
    assert all(len(c) <= 280 for c in chunks)  # un peu de marge avec overlap


def test_chunk_max_chunks_cap():
    long = ". ".join(["Phrase courte"] * 200)
    chunks = chunk_text(long, target_chars=80, max_chunks=5)
    assert len(chunks) == 5


def test_chunk_very_long_sentence_force_split():
    """Une seule phrase plus longue que target → split en force."""
    sentence = "x" * 1500
    chunks = chunk_text(sentence, target_chars=500)
    assert len(chunks) >= 3
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_preserves_information():
    """Concatène les chunks doit contenir les mots clés du texte original."""
    text = (
        "Je m'appelle Mickael. J'habite à Paris. J'aime le café. "
        "Je travaille comme développeur. Mon chat s'appelle Mistral."
    ) * 5
    chunks = chunk_text(text, target_chars=150)
    joined = " ".join(chunks).lower()
    for keyword in ("mickael", "paris", "café", "développeur", "mistral"):
        assert keyword in joined
