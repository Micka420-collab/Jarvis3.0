"""Chunking de longs textes pour préserver la précision sémantique.

Stratégie : split par phrases (regex simple sur ponctuation), puis groupe
par longueur cible avec overlap pour préserver le contexte.

Pour un texte court (< target_chars), on retourne tel quel sans dupliquer.
"""

from __future__ import annotations

import re

_SENT_END = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÉÀÈÙÂÊÎÔÛÄËÏÖÜÇ])")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENT_END.split(text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    *,
    target_chars: int = 600,
    overlap_chars: int = 80,
    max_chunks: int = 16,
) -> list[str]:
    """Renvoie une liste de chunks dont chacun fait ~target_chars caractères.

    Si le texte est plus court que target_chars, retourne [text].
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= target_chars:
        return [text]

    sentences = split_sentences(text) or [text]
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= target_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
                # overlap : on garde la fin du chunk précédent au début du suivant
                if overlap_chars > 0 and len(current) > overlap_chars:
                    current = current[-overlap_chars:].rsplit(" ", 1)[-1] + " " + s
                else:
                    current = s
            else:
                # une seule phrase plus longue que target → split en force
                for i in range(0, len(s), target_chars):
                    chunks.append(s[i : i + target_chars])
                current = ""
        if len(chunks) >= max_chunks:
            break
    if current and len(chunks) < max_chunks:
        chunks.append(current)
    return chunks[:max_chunks]
