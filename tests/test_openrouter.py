"""Tests adapter OpenRouter (conversion tools, parsing réponses).

On stubbe les imports relatifs avant de charger le module.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Crée un faux package "or_pkg" pour que `from .base import LLMAdapter` fonctionne
or_pkg = types.ModuleType("or_pkg")
or_pkg.__path__ = [str(ROOT / "services/llm/app/adapters")]
fake_base = types.ModuleType("or_pkg.base")
fake_base.LLMAdapter = type("LLMAdapter", (), {})
or_pkg.base = fake_base
sys.modules["or_pkg"] = or_pkg
sys.modules["or_pkg.base"] = fake_base

spec = importlib.util.spec_from_file_location(
    "or_pkg.openrouter", ROOT / "services/llm/app/adapters/openrouter.py"
)
or_adapter = importlib.util.module_from_spec(spec)
sys.modules["or_pkg.openrouter"] = or_adapter
spec.loader.exec_module(or_adapter)


def test_to_openai_tools_none():
    assert or_adapter._to_openai_tools(None) is None
    assert or_adapter._to_openai_tools([]) is None


def test_to_openai_tools_converts_anthropic_format():
    anthropic = [{"name": "get_weather", "description": "météo",
                  "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}}}]
    out = or_adapter._to_openai_tools(anthropic)
    assert out == [{"type": "function", "function": {
        "name": "get_weather",
        "description": "météo",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
    }}]


def test_to_openai_tools_default_schema():
    out = or_adapter._to_openai_tools([{"name": "ping"}])
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_from_openai_tool_calls_empty():
    assert or_adapter._from_openai_tool_calls(None) == []
    assert or_adapter._from_openai_tool_calls([]) == []


def test_from_openai_tool_calls_parses():
    oa = [{"id": "call_1", "type": "function",
           "function": {"name": "weather", "arguments": '{"city": "Paris"}'}}]
    out = or_adapter._from_openai_tool_calls(oa)
    assert out == [{"name": "weather", "input": {"city": "Paris"}, "id": "call_1"}]


def test_from_openai_tool_calls_handles_invalid_json():
    oa = [{"id": "x", "function": {"name": "f", "arguments": "not-json"}}]
    out = or_adapter._from_openai_tool_calls(oa)
    assert out[0]["input"] == {}
