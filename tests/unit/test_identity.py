"""Tests IdentityStore (cache des vérifs voix-print)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))

from _shared.events import VoiceIdentityVerified
from app.identity import IdentityStore, SESSION_TTL_S


def make_event(session: str, sim: float, owner: bool) -> VoiceIdentityVerified:
    return VoiceIdentityVerified(
        session_id=session, user_id="u" if owner else None, similarity=sim, is_owner=owner
    )


def test_set_and_get() -> None:
    s = IdentityStore()
    s.set("a", make_event("a", 0.9, True))
    cur = s.get("a")
    assert cur is not None
    assert cur.is_owner is True
    assert cur.similarity == 0.9


def test_owner_authenticated_above_threshold() -> None:
    s = IdentityStore()
    s.set("a", make_event("a", 0.9, True))
    assert s.is_owner_authenticated("a", threshold=0.75, require_challenge=False) is True


def test_owner_not_authenticated_below_threshold() -> None:
    s = IdentityStore()
    s.set("a", make_event("a", 0.7, True))
    assert s.is_owner_authenticated("a", threshold=0.75, require_challenge=False) is False


def test_grey_zone_requires_challenge() -> None:
    s = IdentityStore()
    s.set("a", make_event("a", 0.7, True))
    assert s.is_owner_authenticated("a", threshold=0.65, require_challenge=True) is False
    s.mark_challenge_passed("a")
    assert s.is_owner_authenticated("a", threshold=0.65, require_challenge=True) is True


def test_session_expires() -> None:
    s = IdentityStore()
    s.set("a", make_event("a", 0.9, True))
    cur = s._by_session["a"]
    cur.ts = time.time() - SESSION_TTL_S - 1
    assert s.get("a") is None
