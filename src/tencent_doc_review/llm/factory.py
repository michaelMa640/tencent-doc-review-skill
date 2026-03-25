"""Provider factory for LLM clients."""

from __future__ import annotations

from typing import Any

from .providers.deepseek import DeepSeekClient


def create_llm_client(provider: str = "deepseek", **kwargs: Any):
    normalized = provider.strip().lower()
    if normalized == "deepseek":
        return DeepSeekClient(**kwargs)
    raise ValueError(f"Unsupported LLM provider: {provider}")
