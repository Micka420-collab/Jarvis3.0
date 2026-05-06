"""Tests SpeakerRouter (multi-room audio)."""

from __future__ import annotations

import time

from multiroom import SpeakerRouter  # noqa: E402


def _make_router_with_speakers(speakers: dict) -> SpeakerRouter:
    r = SpeakerRouter.__new__(SpeakerRouter)
    r.speakers = speakers
    r._presence_ts = {}
    r._busy = {sid: False for sid in speakers}
    return r


def test_select_returns_none_when_no_speakers():
    r = _make_router_with_speakers({})
    assert r.select() is None


def test_select_picks_default_when_no_presence():
    r = _make_router_with_speakers({
        "main": {"id": "main", "kind": "browser", "default": True, "room": "any"},
        "kitchen": {"id": "kitchen", "kind": "mqtt", "room": "cuisine"},
    })
    sid, sp = r.select()
    assert sid == "main"


def test_select_picks_speaker_in_occupied_room():
    r = _make_router_with_speakers({
        "main": {"id": "main", "kind": "browser", "default": True, "room": "any"},
        "salon": {"id": "salon", "kind": "snapcast", "room": "salon"},
        "chambre": {"id": "chambre", "kind": "mqtt", "room": "chambre"},
    })
    r.update_presence("salon", time.time())
    sid, _ = r.select()
    assert sid == "salon"


def test_select_skips_busy_speaker():
    r = _make_router_with_speakers({
        "salon_a": {"id": "salon_a", "kind": "snapcast", "room": "salon"},
        "salon_b": {"id": "salon_b", "kind": "snapcast", "room": "salon"},
    })
    r.update_presence("salon", time.time())
    r.mark_speaker("salon_a", busy=True)
    sid, _ = r.select()
    assert sid == "salon_b"


def test_select_uses_most_recent_room():
    r = _make_router_with_speakers({
        "salon": {"id": "salon", "kind": "snapcast", "room": "salon"},
        "chambre": {"id": "chambre", "kind": "mqtt", "room": "chambre"},
    })
    now = time.time()
    r.update_presence("salon", now - 100)
    r.update_presence("chambre", now)  # plus récente
    sid, _ = r.select()
    assert sid == "chambre"
