"""Tests du module challenge phrase."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))

from app import challenge


def test_issue_returns_three_words() -> None:
    phrase = challenge.issue("s1")
    assert len(phrase.split()) == 3


def test_verify_accepts_exact_match() -> None:
    phrase = challenge.issue("s2")
    assert challenge.verify("s2", phrase) is True
    # 2e tentative consommée
    assert challenge.verify("s2", phrase) is False


def test_verify_normalizes_accents_and_case() -> None:
    challenge._PENDING["s3"] = challenge.Challenge(
        phrase="bleu marin quatre", issued_at=time.time()
    )
    assert challenge.verify("s3", "Bleu Marin Quatre.") is True


def test_verify_rejects_wrong_phrase() -> None:
    challenge._PENDING["s4"] = challenge.Challenge(
        phrase="bleu marin quatre", issued_at=time.time()
    )
    assert challenge.verify("s4", "rouge tigre cinq") is False


def test_expired_challenge() -> None:
    challenge._PENDING["s5"] = challenge.Challenge(
        phrase="bleu marin quatre", issued_at=time.time() - 999
    )
    assert challenge.verify("s5", "bleu marin quatre") is False
    assert challenge.has_pending("s5") is None
