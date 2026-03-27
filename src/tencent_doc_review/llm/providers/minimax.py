"""MiniMax provider built on the OpenAI-compatible API surface."""

from __future__ import annotations

from typing import Any, Optional

from .openai import OpenAIClient


class MiniMaxClient(OpenAIClient):
    """Async wrapper for MiniMax OpenAI-compatible chat completions."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.minimaxi.com/v1",
        model: str = "MiniMax-M2.7",
        timeout: int = 30,
        client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            client=client,
        )

    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ):
        # MiniMax is more stable for structured review tasks with a lower default
        # temperature, while still respecting the provider's valid range.
        bounded_temperature = min(max(float(temperature), 0.01), 1.0)
        return await super().analyze(
            prompt=prompt,
            analysis_type=analysis_type,
            temperature=bounded_temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
