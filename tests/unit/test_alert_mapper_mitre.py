"""Tests du contexte MITRE ATT&CK dans alert_mapper."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "security"))

from app.alert_mapper import alert_to_speech


def test_mitre_tactic_translated() -> None:
    speech = alert_to_speech(
        {
            "severity": "high",
            "rule": "scan détecté",
            "host": "192.168.1.42",
            "summary": "",
            "raw": {"mitre": {"tactic": ["TA0007"], "technique": []}},
        }
    )
    assert "découverte du réseau" in speech


def test_mitre_technique_translated() -> None:
    speech = alert_to_speech(
        {
            "severity": "critical",
            "rule": "ssh brute force",
            "host": "h",
            "summary": "",
            "raw": {"rule": {"mitre": {"tactic": [], "technique": ["T1110"]}}},
        }
    )
    assert "force brute" in speech


def test_no_mitre_no_parens() -> None:
    speech = alert_to_speech(
        {"severity": "info", "rule": "x", "host": "h", "summary": ""}
    )
    assert "(" not in speech
