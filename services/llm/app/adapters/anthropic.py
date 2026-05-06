"""Adapter Anthropic Claude (cloud)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from .base import LLMAdapter


class AnthropicAdapter(LLMAdapter):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY manquant")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> dict:
        kwargs = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        resp = await self.client.messages.create(**kwargs)
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"name": block.name, "input": block.input, "id": block.id})
        return {
            "text": "".join(text_parts),
            "tool_calls": tool_calls,
            "stop_reason": resp.stop_reason or "stop",
        }

    async def complete_stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk
