from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> dict:
        """Retourne {"text": str, "tool_calls": [...]?, "stop_reason": str}."""

    @abstractmethod
    async def complete_stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        """Stream de tokens texte."""
