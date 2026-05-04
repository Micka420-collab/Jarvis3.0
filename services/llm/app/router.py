"""Routeur LLM : choisit le provider en fonction de l'env."""

from __future__ import annotations

import os

from .adapters.base import LLMAdapter


def make_adapter(provider: str | None = None) -> LLMAdapter:
    provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
    if provider == "anthropic":
        from .adapters.anthropic import AnthropicAdapter

        return AnthropicAdapter()
    if provider == "anthropic-vision":
        from .adapters.anthropic_vision import AnthropicVisionAdapter

        return AnthropicVisionAdapter()
    if provider == "mistral":
        from .adapters.mistral import MistralAdapter

        return MistralAdapter()
    from .adapters.ollama import OllamaAdapter

    return OllamaAdapter()
