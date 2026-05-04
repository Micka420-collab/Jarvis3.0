"""Mapping des alertes Argus → phrases TTS courtes en français.

Enrichit avec contexte MITRE ATT&CK quand c'est dispo dans la règle.
"""

from __future__ import annotations

SEVERITY_PHRASES = {
    "critical": "Alerte critique",
    "high": "Alerte importante",
    "medium": "Alerte modérée",
    "low": "Alerte mineure",
    "info": "Information",
}

# Catégories MITRE ATT&CK les plus fréquentes en SOC, traduites en français
MITRE_TACTICS_FR = {
    "TA0001": "accès initial",
    "TA0002": "exécution",
    "TA0003": "persistance",
    "TA0004": "élévation de privilèges",
    "TA0005": "évasion défensive",
    "TA0006": "vol d'identifiants",
    "TA0007": "découverte du réseau",
    "TA0008": "déplacement latéral",
    "TA0009": "collecte de données",
    "TA0010": "exfiltration",
    "TA0011": "command and control",
    "TA0040": "impact",
}

# Techniques fréquemment vues côté Wazuh/Suricata
MITRE_TECHNIQUES_FR = {
    "T1046": "scan de ports",
    "T1110": "force brute",
    "T1078": "compte valide compromis",
    "T1190": "exploitation d'une appli web",
    "T1059": "exécution de commande shell",
    "T1486": "rançongiciel",
    "T1566": "phishing",
    "T1071": "trafic C2 chiffré",
    "T1041": "exfiltration via C2",
    "T1083": "découverte de fichiers",
}


def _mitre_context(alert: dict) -> str:
    parts: list[str] = []
    raw = alert.get("raw") or {}
    rule = (raw.get("rule") if isinstance(raw, dict) else None) or {}
    mitre = rule.get("mitre") if isinstance(rule, dict) else None
    if not mitre and isinstance(raw, dict):
        mitre = raw.get("mitre")
    if not isinstance(mitre, dict):
        return ""
    for tac in mitre.get("tactic", []) or []:
        label = MITRE_TACTICS_FR.get(tac, tac)
        parts.append(label)
    for tech in mitre.get("technique", []) or []:
        label = MITRE_TECHNIQUES_FR.get(tech, tech)
        if label not in parts:
            parts.append(label)
    if not parts:
        return ""
    return " (" + ", ".join(parts[:3]) + ")"


def alert_to_speech(alert: dict) -> str:
    sev = (alert.get("severity") or "info").lower()
    rule = alert.get("rule", "événement")
    host = alert.get("host", "un hôte")
    summary = alert.get("summary", "")
    head = SEVERITY_PHRASES.get(sev, "Alerte")
    mitre = _mitre_context(alert)
    base = f"{head} sur {host} — {rule}{mitre}."
    if summary:
        base += f" {summary}"
    # tronqué pour TTS court
    return base[:240]
