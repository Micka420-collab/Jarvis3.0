"""Adapter Mistral (cloud)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from mistralai import Mistral

from .base import LLMAdapter


class MistralAdapter(LLMAdapter):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY manquant")
        self.client = Mistral(api_key=api_key)
        self.model = model or os.getenv("MISTRAL_MODEL", "mistral-large-latest")

    def _build(self, system: str, messages: list[dict]) -> list[dict]:
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
        resp = await self.client.chat.complete_async(
            model=self.model,
            messages=self._build(system, messages),
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        choice = resp.choices[0]
        msg = choice.message
        return {
            "text": msg.content or "",
            "tool_calls": [
                {"name": tc.function.name, "input": tc.function.arguments, "id": tc.id}
                for tc in (msg.tool_calls or [])
            ],
            "stop_reason": choice.finish_reason or "stop",
        }

    async def complete_stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.stream_async(
            model=self.model,
            messages=self._build(system, messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )
        async for chunk in stream:
            delta = chunk.data.choices[0].delta.content
            if delta:
                yield delta
