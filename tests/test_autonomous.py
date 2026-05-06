"""Tests pour le mode agent autonome."""

from __future__ import annotations

import pytest

from autonomous import is_autonomous_request, run_autonomous  # noqa: E402


@pytest.mark.parametrize(
    "text,expected",
    [
        ("organise mes mails et lance la routine soir", True),
        ("gère mon agenda demain", True),
        ("prépare la maison pour la soirée", True),
        ("ouvre les volets puis allume le café et lance la radio puis chauffe la salle de bain", True),
        ("allume la lumière du salon", False),
        ("quel temps fait-il ?", False),
    ],
)
def test_is_autonomous_request(text, expected):
    assert is_autonomous_request(text) is expected


@pytest.mark.asyncio
async def test_run_autonomous_completes_without_tools():
    async def call_llm(history):
        # 1er tour : pas de tool, juste un texte → halt completed
        return {"text": "Voilà, c'est fait.", "tool_calls": [], "stop_reason": "stop"}

    async def dispatch_tool(name, args, ctx):
        return {"ok": True}

    def gate_admin(_session, _name):
        return True, None

    result = await run_autonomous([{"role": "user", "content": "test"}],
                                  call_llm, dispatch_tool, gate_admin, ctx={})
    assert result["halt_reason"] == "completed"
    assert result["reply"] == "Voilà, c'est fait."
    assert result["steps"] == []


@pytest.mark.asyncio
async def test_run_autonomous_chains_tools():
    """Simule un LLM qui appelle un tool, puis termine au tour suivant."""
    calls = {"n": 0}

    async def call_llm(history):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"text": "j'enchaîne", "tool_calls": [{"name": "light_on", "input": {"room": "salon"}, "id": "t1"}], "stop_reason": "tool_use"}
        return {"text": "fini", "tool_calls": [], "stop_reason": "stop"}

    async def dispatch_tool(name, args, ctx):
        return {"ok": True, "tool": name, "args": args}

    def gate_admin(_s, _n):
        return True, None

    result = await run_autonomous([{"role": "user", "content": "x"}],
                                  call_llm, dispatch_tool, gate_admin, ctx={})
    assert result["halt_reason"] == "completed"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["tool"] == "light_on"


@pytest.mark.asyncio
async def test_run_autonomous_denies_admin():
    async def call_llm(history):
        return {"text": "tente", "tool_calls": [{"name": "unlock_door", "input": {}, "id": "x"}], "stop_reason": "tool_use"}

    async def dispatch_tool(*_a, **_k):
        return {"ok": True}

    def gate_admin(_s, _n):
        return False, "Confirme avec : citron jaune"

    result = await run_autonomous([{"role": "user", "content": "ouvre la porte"}],
                                  call_llm, dispatch_tool, gate_admin, ctx={})
    assert result["halt_reason"] == "denied"
    assert "citron jaune" in result["reply"]


@pytest.mark.asyncio
async def test_run_autonomous_max_steps():
    """Le LLM appelle infiniment des tools — on s'arrête à max_steps."""
    async def call_llm(history):
        return {"text": "encore", "tool_calls": [{"name": "loop", "input": {}, "id": "z"}], "stop_reason": "tool_use"}

    async def dispatch_tool(*_a, **_k):
        return {"ok": True}

    def gate_admin(_s, _n):
        return True, None

    result = await run_autonomous([{"role": "user", "content": "test"}],
                                  call_llm, dispatch_tool, gate_admin, ctx={}, max_steps=3)
    assert result["halt_reason"] == "max_steps"
    assert len(result["steps"]) == 3
