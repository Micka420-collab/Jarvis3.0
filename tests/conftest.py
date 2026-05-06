"""Fixtures pytest pour les tests unitaires Jarvis.

Ajoute chaque service comme namespace ; les tests importent ensuite
en utilisant le nom du service (`from orchestrator_app.autonomous import ...`).
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _register_service_namespace(svc: str) -> None:
    """Crée un module fictif `<svc>_app` qui pointe sur services/<svc>/app/."""
    app_dir = ROOT / "services" / svc / "app"
    if not app_dir.is_dir():
        return
    if str(app_dir.parent) not in sys.path:
        sys.path.insert(0, str(app_dir.parent))
    # Importe le package "app" et l'expose sous un alias unique
    sys.path.insert(0, str(app_dir))


for svc in ("orchestrator", "voice", "llm", "memory", "iot", "security", "agents", "vision"):
    _register_service_namespace(svc)


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    yield monkeypatch
