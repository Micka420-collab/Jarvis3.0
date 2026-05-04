"""Cache des dernières vérifications voix-print par session.

Le service voice publie `voice.identity.verified` à chaque utterance.
L'orchestrator consomme et garde l'état courant pour gater les commandes admin.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from _shared.bus import EventBus
from _shared.events import STREAM_VOICE_IDENTITY, VoiceIdentityVerified

log = logging.getLogger("orchestrator.identity")

# expirée après ce délai si on ne reçoit pas de nouvelle vérif
SESSION_TTL_S = 60.0


@dataclass
class Identity:
    user_id: str | None
    similarity: float
    is_owner: bool
    challenge_passed: bool
    ts: float


class IdentityStore:
    def __init__(self) -> None:
        self._by_session: dict[str, Identity] = {}

    def set(self, session_id: str, ev: VoiceIdentityVerified) -> None:
        existing = self._by_session.get(session_id)
        challenge_passed = bool(existing and existing.challenge_passed)
        self._by_session[session_id] = Identity(
            user_id=ev.user_id,
            similarity=ev.similarity,
            is_owner=ev.is_owner,
            challenge_passed=challenge_passed if not ev.is_owner else challenge_passed,
            ts=time.time(),
        )

    def mark_challenge_passed(self, session_id: str) -> None:
        cur = self._by_session.get(session_id)
        if cur is None:
            self._by_session[session_id] = Identity(None, 0.0, False, True, time.time())
        else:
            cur.challenge_passed = True
            cur.ts = time.time()

    def get(self, session_id: str) -> Identity | None:
        cur = self._by_session.get(session_id)
        if cur is None:
            return None
        if time.time() - cur.ts > SESSION_TTL_S:
            self._by_session.pop(session_id, None)
            return None
        return cur

    def is_owner_authenticated(
        self,
        session_id: str,
        threshold: float,
        require_challenge: bool,
    ) -> bool:
        cur = self.get(session_id)
        if cur is None:
            return False
        if not cur.is_owner:
            return False
        if cur.similarity < threshold:
            return False
        if require_challenge and not cur.challenge_passed:
            return False
        return True


async def consume_identity_events(bus: EventBus, store: IdentityStore) -> None:
    async for _id, ev in bus.consume(
        STREAM_VOICE_IDENTITY, "orch-identity", "orch-identity-1", VoiceIdentityVerified
    ):
        try:
            store.set(ev.session_id, ev)
            log.debug(
                "identity session=%s is_owner=%s sim=%.2f",
                ev.session_id,
                ev.is_owner,
                ev.similarity,
            )
        except Exception as e:
            log.warning("identity event KO: %s", e)
