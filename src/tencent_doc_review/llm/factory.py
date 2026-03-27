"""Provider factory and runtime resolution helpers for LLM clients."""

from __future__ import annotations

from typing import Any, Optional

from .providers.deepseek import DeepSeekClient
from .providers.minimax import MiniMaxClient
from .providers.mock import MockLLMClient
from .providers.openai import OpenAIClient

SUPPORTED_PROVIDERS = ("deepseek", "minimax", "mock", "openai")


def resolve_llm_settings(
    settings: Any,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict[str, Any]:
    normalized = (provider or getattr(settings, "llm_provider", "deepseek")).strip().lower()

    if normalized == "deepseek":
        resolved_api_key = api_key or getattr(settings, "deepseek_api_key", "") or getattr(settings, "llm_api_key", "")
        resolved_base_url = base_url or getattr(settings, "deepseek_base_url", "") or getattr(settings, "llm_base_url", "")
        resolved_model = model or getattr(settings, "deepseek_model", "") or getattr(settings, "llm_model", "")
    elif normalized == "minimax":
        resolved_api_key = api_key or getattr(settings, "minimax_api_key", "") or getattr(settings, "llm_api_key", "")
        resolved_base_url = base_url or getattr(settings, "minimax_base_url", "") or getattr(settings, "llm_base_url", "")
        resolved_model = model or getattr(settings, "minimax_model", "") or getattr(settings, "llm_model", "")
    else:
        resolved_api_key = api_key or getattr(settings, "llm_api_key", "") or getattr(settings, "deepseek_api_key", "")
        resolved_base_url = base_url or getattr(settings, "llm_base_url", "") or getattr(settings, "deepseek_base_url", "")
        resolved_model = model or getattr(settings, "llm_model", "") or getattr(settings, "deepseek_model", "")

    return {
        "provider": normalized,
        "api_key": resolved_api_key,
        "base_url": resolved_base_url,
        "model": resolved_model,
        "timeout": int(timeout if timeout is not None else getattr(settings, "request_timeout", 30)),
    }


def create_llm_client(provider: str = "deepseek", **kwargs: Any):
    normalized = (provider or "deepseek").strip().lower()
    if normalized == "deepseek":
        return DeepSeekClient(**kwargs)
    if normalized == "minimax":
        timeout = kwargs.get("timeout")
        if timeout is None or int(timeout) < 120:
            kwargs["timeout"] = 120
        return MiniMaxClient(**kwargs)
    if normalized == "mock":
        return MockLLMClient()
    if normalized == "openai":
        return OpenAIClient(**kwargs)
    raise ValueError(
        f"Unsupported LLM provider: {provider}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
    )
