"""Tests RAG (memory-augmented prompting)."""

from __future__ import annotations

import pytest

from rag import format_context  # noqa: E402


def test_format_context_empty():
    assert format_context([]) == ""


def test_format_context_filters_blank_text():
    out = format_context([{"text": "", "score": 0.9}, {"text": "vrai souvenir", "score": 0.7}])
    assert "vrai souvenir" in out
    assert "[0.70]" in out


def test_format_context_preserves_order_and_scores():
    out = format_context([
        {"text": "premier", "score": 0.95},
        {"text": "second", "score": 0.80},
    ])
    lines = out.splitlines()
    assert "Souvenirs pertinents" in out
    assert lines.index("- [0.95] premier") < lines.index("- [0.80] second")
