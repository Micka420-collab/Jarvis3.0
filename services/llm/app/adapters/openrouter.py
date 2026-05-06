"""Adapter OpenRouter — accès unifié à 200+ modèles via une seule clé API.

OpenRouter (https://openrouter.ai) est compatible OpenAI : on POST
sur /chat/completions, et tu choisis le modèle via le champ `model`.

Exemples de modèles :
  anthropic/claude-sonnet-4-6      → Claude Sonnet 4.6
  anthropic/claude-opus-4-7        → Claude Opus 4.7
  openai/gpt-4o                    → GPT-4o
  meta-llama/llama-3.3-70b-instruct → Llama 3.3 70B
  google/gemini-2.0-flash-exp      → Gemini 2.0 Flash
  mistralai/mistral-large          → Mistral Large

Avantage : une seule clé pour tous les providers, fallback automatique,
rate limits cumulés. Inconvénient : marge OpenRouter (~5-10%).

Le tool calling est supporté en passant `tools` au format OpenAI ; on
convertit depuis le format Anthropic-like utilisé par l'orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator

import httpx

from .base import LLMAdapter

log = logging.getLogger("llm.openrouter")

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def _to_openai_tools(tools: list[dict] | None) -> list[dict] | None:
    """Convertit le format Anthropic (`name`, `input_schema`, `description`)
    vers le format OpenAI (`type:"function"`, `function:{name,description,parameters}`)."""
    if not tools:
        return None
    out = []
    for t in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
        )
    return out


def _from_openai_tool_calls(calls: list[dict] | None) -> list[dict]:
    """OpenAI : choices[0].message.tool_calls = [{id, type:'function', function:{name, arguments(JSON-str)}}]
    On convertit en {name, input(dict), id} comme Anthropic."""
    if not calls:
        return []
    out = []
    for c in calls:
        fn = c.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except Exception:
            args = {}
        out.append({"name": fn.get("name", ""), "input": args, "id": c.get("id", "")})
    return out


class OpenRouterAdapter(LLMAdapter):
    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY manquant")
        self.api_key = api_key
        self.model = model or os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")
        self.referer = os.getenv("OPENROUTER_HTTP_REFERER", "https://jarvis.local")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "Jarvis 3.0")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Headers spécifiques OpenRouter pour apparaître dans leurs stats
            "HTTP-Referer": self.referer,
            "X-Title": self.app_name,
        }

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> dict:
        # Préfixer le système au début des messages (format OpenAI)
        oa_messages: list[dict] = []
        if system:
            oa_messages.append({"role": "system", "content": system})
        oa_messages.extend(messages)

        body: dict = {
            "model": self.model,
            "messages": oa_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        oa_tools = _to_openai_tools(tools)
        if oa_tools:
            body["tools"] = oa_tools

        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(f"{OPENROUTER_BASE}/chat/completions", json=body, headers=self._headers)
            if r.status_code >= 400:
                log.error("openrouter %s : %s", r.status_code, r.text[:500])
                r.raise_for_status()
            data = r.json()

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        return {
            "text": msg.get("content") or "",
            "tool_calls": _from_openai_tool_calls(msg.get("tool_calls")),
            "stop_reason": choice.get("finish_reason", "stop"),
        }

    async def complete_stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        oa_messages: list[dict] = []
        if system:
            oa_messages.append({"role": "system", "content": system})
        oa_messages.extend(messages)

        body = {
            "model": self.model,
            "messages": oa_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as c:
            async with c.stream(
                "POST",
                f"{OPENROUTER_BASE}/chat/completions",
                json=body,
                headers=self._headers,
            ) as resp:
                if resp.status_code >= 400:
                    txt = await resp.aread()
                    log.error("openrouter stream %s : %s", resp.status_code, txt[:500])
                    return
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload in {"", "[DONE]"}:
                        continue
                    try:
                        chunk = json.loads(payload)
                    except Exception:
                        continue
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                    tok = delta.get("content")
                    if tok:
                        yield tok
