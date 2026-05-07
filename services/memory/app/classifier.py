"""Classifieur heuristique de la catégorie d'un fait.

Détecte sans LLM la nature probable d'un texte mémorisé pour permettre des
filtres rapides (ex: ne récupérer que les `preference` quand on prépare un
cadeau, ou que les `event` quand on parle d'un souvenir précis).

Catégories :
  - preference   : "j'aime", "j'adore", "je déteste", "préfère"
  - fact         : info objective ("X est Y", "habite à", "travaille chez")
  - event        : passé daté ("hier", "la semaine dernière", "en 2024")
  - skill_observation : observation pour learning ("toujours à 19h",
                        "chaque matin")
  - conversation : dialogue ("a dit que", "m'a demandé")
  - other        : reste

Aucune dépendance ML — pure heuristique regex/keywords FR+EN.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    ("preference", [
        re.compile(r"\b(j'?aime|j'?adore|je déteste|je préfère|je n'?aime pas|i (?:like|love|hate|prefer))\b", re.I),
        re.compile(r"\b(mon (?:plat|film|livre|sport) préféré|ma (?:couleur|musique) préférée|favorite)\b", re.I),
    ]),
    ("event", [
        re.compile(r"\b(hier|avant-hier|la semaine dernière|le mois dernier|en \d{4}|yesterday|last (?:week|month|year))\b", re.I),
        re.compile(r"\b(je suis (?:allé|partie?|parti) à|j'?ai (?:visité|rencontré))\b", re.I),
    ]),
    ("skill_observation", [
        re.compile(r"\b(toujours|chaque (?:matin|soir|jour|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)|tous les jours|every day)\b", re.I),
        re.compile(r"\b(à \d{1,2}h\d{0,2}|at \d{1,2}(?:am|pm))\b", re.I),
    ]),
    ("conversation", [
        re.compile(r"\b(a dit que|m'a (?:dit|demandé|raconté)|told me|asked me)\b", re.I),
    ]),
    ("fact", [
        re.compile(r"\b(habite|vit à|travaille (?:chez|pour|à)|s'?appelle|est (?:un|une|né|née))\b", re.I),
        re.compile(r"\b(lives in|works (?:at|for)|is named|was born)\b", re.I),
    ]),
]


def classify(text: str) -> str:
    """Renvoie la 1re catégorie qui matche, ou 'other'."""
    if not text or not text.strip():
        return "other"
    for kind, patterns in _PATTERNS:
        for pat in patterns:
            if pat.search(text):
                return kind
    return "other"


def auto_importance(text: str, kind: str) -> float:
    """Heuristique d'importance par défaut selon la catégorie + signaux."""
    base = {
        "preference": 0.7,            # les préférences sont précieuses long-terme
        "fact": 0.6,
        "event": 0.4,                 # les événements vieillissent vite
        "skill_observation": 0.65,
        "conversation": 0.3,
        "other": 0.5,
    }.get(kind, 0.5)
    # Boost si l'utilisateur a signalé son importance avec des marqueurs forts
    t = text.lower()
    if any(w in t for w in ("important", "n'oublie pas", "rappelle-toi", "ne pas oublier", "remember")):
        base = min(1.0, base + 0.2)
    if any(w in t for w in ("anniversaire", "naissance", "mariage", "décès", "birthday")):
        base = min(1.0, base + 0.15)
    return round(base, 3)
