"""Tests unitaires alert_mapper (sans dépendances réseau)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "security"))

from app.alert_mapper import alert_to_speech


def test_critical_alert_mentions_severity_and_host() -> None:
    speech = alert_to_speech(
        {"severity": "critical", "rule": "port scan", "host": "192.168.1.42", "summary": "ports 22 80"}
    )
    assert "critique" in speech.lower()
    assert "192.168.1.42" in speech
    assert "port scan" in speech


def test_unknown_severity_falls_back() -> None:
    speech = alert_to_speech({"severity": "unknown", "host": "h", "rule": "r"})
    assert "alerte" in speech.lower() or "h" in speech


def test_truncated_to_240() -> None:
    long = "x" * 1000
    speech = alert_to_speech({"severity": "info", "rule": "r", "host": "h", "summary": long})
    assert len(speech) <= 240
