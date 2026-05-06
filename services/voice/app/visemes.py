"""Mapping phonèmes IPA → visèmes Oculus 15 (compatibles ARKit/blendshapes).

Référence: https://developer.oculus.com/documentation/native/audio-ovrlipsync-viseme-reference/
"""

from __future__ import annotations

import math

import numpy as np

# Visèmes Oculus 15 standards
VISEMES = [
    "sil", "PP", "FF", "TH", "DD", "kk", "CH",
    "SS", "nn", "RR", "aa", "E", "ih", "oh", "ou",
]

# Approximations IPA simplifiées
IPA_TO_VISEME: dict[str, str] = {
    # silence
    " ": "sil", ".": "sil", ",": "sil",
    # bilabials
    "p": "PP", "b": "PP", "m": "PP",
    # labiodentals
    "f": "FF", "v": "FF",
    # dentals
    "θ": "TH", "ð": "TH",
    # alveolars
    "t": "DD", "d": "DD", "z": "SS", "s": "SS", "n": "nn", "l": "nn",
    # velars
    "k": "kk", "g": "kk", "ŋ": "kk",
    # post-alveolars
    "ʃ": "CH", "ʒ": "CH", "tʃ": "CH", "dʒ": "CH",
    # rhotics
    "r": "RR", "ʁ": "RR", "ɾ": "RR",
    # vowels
    "a": "aa", "ɑ": "aa", "ɐ": "aa",
    "ɛ": "E", "e": "E", "ə": "E",
    "i": "ih", "ɪ": "ih", "y": "ih",
    "o": "oh", "ɔ": "oh",
    "u": "ou", "ʊ": "ou", "ø": "ou", "œ": "ou", "ɥ": "ou",
}


def viseme_for_phoneme(p: str) -> str:
    if not p:
        return "sil"
    return IPA_TO_VISEME.get(p, IPA_TO_VISEME.get(p[0], "E"))


def amplitude_to_jaw(pcm16_bytes: bytes) -> float:
    """RMS d'un chunk PCM int16 → ouverture mâchoire 0..1.

    Fallback si on n'a pas les phonèmes Piper pour ce chunk.
    """
    if not pcm16_bytes:
        return 0.0
    arr = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if arr.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(arr * arr)))
    # compression douce vers [0, 1] (rms typique 0.05..0.3)
    return float(min(1.0, math.tanh(rms * 6.0)))
