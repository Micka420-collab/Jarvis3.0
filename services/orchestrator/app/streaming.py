"""Découpe un flux de tokens LLM en phrases complètes pour TTS streaming.

Émet une phrase dès qu'on rencontre un délimiteur de fin (.!?\n) suivi d'un
espace ou de la fin. Évite de couper sur des abréviations courantes (M., Mme.,
etc.).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterable

# motif de fin de phrase : ponctuation finale + (espace, \n, ou fin)
END_RE = re.compile(r"([.!?…]+)(\s|$)")

# abréviations qu'on ne casse pas (élargir si besoin)
NO_BREAK_AFTER = {"m.", "mme.", "dr.", "p.ex.", "etc.", "cf.", "p.s.", "n°"}


def is_safe_break(buffer: str, end_idx: int) -> bool:
    # cherche le dernier mot avant le break
    word_match = re.search(r"(\S+)$", buffer[: end_idx + 1])
    if not word_match:
        return True
    last_word = word_match.group(1).lower()
    return last_word not in NO_BREAK_AFTER


async def stream_sentences(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield sentences as they become complete, plus the trailing fragment at end."""
    buf = ""
    async for tok in tokens:
        if not tok:
            continue
        buf += tok
        # itère sur tous les breaks possibles dans le buffer
        while True:
            m = END_RE.search(buf)
            if not m:
                break
            end_idx = m.end(1) - 1  # index inclusif de la dernière ponctuation
            if not is_safe_break(buf, end_idx):
                # avance la recherche après ce point
                later = END_RE.search(buf, m.end())
                if not later:
                    break
                m = later
                end_idx = m.end(1) - 1
            sentence = buf[: end_idx + 1].strip()
            buf = buf[m.end():]
            if sentence:
                yield sentence
    if buf.strip():
        yield buf.strip()


def split_text_into_sentences(text: str) -> Iterable[str]:
    """Version sync utile pour les tests."""
    out: list[str] = []
    buf = text
    while True:
        m = END_RE.search(buf)
        if not m:
            break
        end_idx = m.end(1) - 1
        if not is_safe_break(buf, end_idx):
            later = END_RE.search(buf, m.end())
            if not later:
                break
            m = later
            end_idx = m.end(1) - 1
        out.append(buf[: end_idx + 1].strip())
        buf = buf[m.end():]
    if buf.strip():
        out.append(buf.strip())
    return out
