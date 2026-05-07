"""Tests RAG (memory-augmented prompting)."""

from __future__ import annotations

from rag import format_context  # noqa: E402


def test_format_context_empty():
    assert format_context([]) == ""


def test_format_context_filters_blank_text():
    out = format_context([
        {"text": "", "score": 0.9, "kind": "fact"},
        {"text": "vrai souvenir", "score": 0.7, "kind": "fact"},
    ])
    assert "vrai souvenir" in out
    assert "0.70" in out
    # le kind doit apparaître dans le formatage
    assert "fact" in out


def test_format_context_preserves_order_and_scores():
    out = format_context([
        {"text": "premier", "score": 0.95, "kind": "preference"},
        {"text": "second", "score": 0.80, "kind": "fact"},
    ])
    lines = out.splitlines()
    assert "Souvenirs pertinents" in out
    # ordre conservé : "premier" doit apparaître avant "second"
    line1 = next(line for line in lines if "premier" in line)
    line2 = next(line for line in lines if "second" in line)
    assert lines.index(line1) < lines.index(line2)
    # nouvelle structure : [kind · score] text
    assert "[preference · 0.95]" in line1
    assert "[fact · 0.80]" in line2


def test_format_context_default_kind():
    """Si 'kind' absent, fallback sur 'fact'."""
    out = format_context([{"text": "hello", "score": 0.5}])
    assert "fact" in out
