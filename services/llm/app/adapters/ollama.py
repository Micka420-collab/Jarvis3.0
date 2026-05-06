"""Adapter Ollama (LLM local)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from .base import LLMAdapter


class OllamaAdapter(LLMAdapter):
    def __init__(self, model: str | None = None) -> None:
        self.host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        self.model = model or os.getenv("LLM_MODEL", "llama3.1:8b")

    def _build_messages(self, system: str, messages: list[dict]) -> list[dict]:
        out = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": self._build_messages(system, messages),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{self.host}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message", {})
        return {
            "text": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls", []),
            "stop_reason": data.get("done_reason", "stop"),
        }

    async def complete_stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        import json

        payload = {
            "model": self.model,
            "messages": self._build_messages(system, messages),
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
