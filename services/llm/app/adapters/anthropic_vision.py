"""Adapter Claude Vision : injecte un screenshot caméra dans le prompt LLM.

Utilisé quand l'orchestrator détecte que la requête est multimodale
(« qu'est-ce que tu vois », « est-ce qu'il y a quelqu'un derrière moi », etc.).
Récupère la dernière frame d'une caméra Frigate et l'envoie à Claude avec
le bloc `image` au format Anthropic.
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import AsyncIterator

import httpx
from anthropic import AsyncAnthropic

from .base import LLMAdapter

log = logging.getLogger("llm.anthropic-vision")


class AnthropicVisionAdapter(LLMAdapter):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY manquant")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
        self.frigate_api = os.getenv("FRIGATE_API_URL", "http://frigate:5000")

    async def _fetch_camera_jpg(self, camera: str | None) -> bytes | None:
        if not camera:
            return None
        try:
            async with httpx.AsyncClient(timeout=2.5) as c:
                r = await c.get(f"{self.frigate_api}/api/{camera}/latest.jpg")
                if r.status_code == 200:
                    return r.content
        except Exception as e:
            log.warning("frigate fetch failed: %s", e)
        return None

    @staticmethod
    def _img_block(jpg: bytes) -> dict:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(jpg).decode("ascii"),
            },
        }

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> dict:
        # le caller (orchestrator) peut passer une "camera" dans le contenu
        # du dernier message system : "vision_camera=<nom>"
        camera = None
        for m in messages:
            if m.get("role") == "system":
                continue
            content = m.get("content", "")
            if isinstance(content, str) and "vision_camera=" in content:
                camera = content.split("vision_camera=")[-1].split()[0].strip()

        # injecte l'image dans le dernier message user
        if camera and messages:
            jpg = await self._fetch_camera_jpg(camera)
            if jpg is not None:
                last = messages[-1]
                if isinstance(last.get("content"), str):
                    last["content"] = [
                        self._img_block(jpg),
                        {"type": "text", "text": last["content"]},
                    ]

        kwargs: dict = {
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
        # streaming sans vision (pas implémenté ici, fallback sur Anthropic standard)
        from .anthropic import AnthropicAdapter

        async for tok in AnthropicAdapter().complete_stream(
            system, messages, max_tokens, temperature
        ):
            yield tok
