"""Provider factory for LLM clients."""

from __future__ import annotations

from typing import Any

from .providers.deepseek import DeepSeekClient
from .providers.mock import MockLLMClient
from .providers.openai import OpenAIClient

SUPPORTED_PROVIDERS = ("deepseek", "mock", "openai")

def create_llm_client(provider: str = "deepseek", **kwargs: Any):
    normalized = (provider or "deepseek").strip().lower()
    if normalized == "deepseek":
        return DeepSeekClient(**kwargs)
    if normalized == "mock":
        return MockLLMClient()
    if normalized == "openai":
        return OpenAIClient(**kwargs)
    raise ValueError(
        f"Unsupported LLM provider: {provider}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
    )
