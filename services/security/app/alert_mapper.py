"""Mapping des alertes Argus → phrases TTS courtes en français."""

from __future__ import annotations

SEVERITY_PHRASES = {
    "critical": "Alerte critique",
    "high": "Alerte importante",
    "medium": "Alerte modérée",
    "low": "Alerte mineure",
    "info": "Information",
}


def alert_to_speech(alert: dict) -> str:
    sev = (alert.get("severity") or "info").lower()
    rule = alert.get("rule", "événement")
    host = alert.get("host", "un hôte")
    summary = alert.get("summary", "")
    head = SEVERITY_PHRASES.get(sev, "Alerte")
    base = f"{head} sur {host} — {rule}."
    if summary:
        base += f" {summary}"
    # tronqué pour TTS court
    return base[:240]
