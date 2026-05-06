"""Génère et vérifie des challenge phrases dynamiques pour les commandes admin.

Anti-replay simple: la phrase change à chaque demande.
Anti-deepfake basique: la phrase combine 3 mots non triviaux qu'un attaquant
n'aurait probablement pas pré-enregistré (sauf attaque ciblée).
"""

from __future__ import annotations

import random
import time
import unicodedata
from dataclasses import dataclass

ADJECTIVES = [
    "bleu", "rouge", "noir", "vert", "or", "blanc",
    "rapide", "calme", "vif", "ancien", "doux", "long",
]
NOUNS = [
    "marin", "tigre", "soleil", "vent", "vaisseau", "écho",
    "phare", "renard", "carbone", "miroir", "horizon", "récif",
]
NUMBERS = [
    "deux", "quatre", "sept", "neuf", "onze", "treize",
    "seize", "dix-huit", "vingt", "trente", "quarante", "soixante",
]


@dataclass
class Challenge:
    phrase: str
    issued_at: float


_PENDING: dict[str, Challenge] = {}
TTL_S = 30.0


def _normalize(s: str) -> str:
    s = s.lower().strip()
    # supprime accents et ponctuation
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return "".join(c for c in s if c.isalnum() or c.isspace())


def issue(session_id: str) -> str:
    phrase = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {random.choice(NUMBERS)}"
    _PENDING[session_id] = Challenge(phrase=phrase, issued_at=time.time())
    return phrase


def has_pending(session_id: str) -> str | None:
    ch = _PENDING.get(session_id)
    if ch is None:
        return None
    if time.time() - ch.issued_at > TTL_S:
        _PENDING.pop(session_id, None)
        return None
    return ch.phrase


def verify(session_id: str, transcript: str) -> bool:
    ch = _PENDING.get(session_id)
    if ch is None:
        return False
    if time.time() - ch.issued_at > TTL_S:
        _PENDING.pop(session_id, None)
        return False
    expected = _normalize(ch.phrase)
    got = _normalize(transcript)
    if expected in got:
        _PENDING.pop(session_id, None)
        return True
    return False
