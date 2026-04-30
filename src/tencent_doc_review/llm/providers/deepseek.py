"""DeepSeek provider implementation."""

from __future__ import annotations

from typing import Any, Optional

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback for lean environments
    httpx = None

from ..base import LLMCapabilities, LLMResponse, UsageInfo, WebSearchResponse


class DeepSeekClient:
    """Async wrapper around the DeepSeek chat completions API."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout: int = 30,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            provider="deepseek",
            model=self.model,
            supports_native_web_search=False,
            notes="DeepSeek client currently only implements chat completions in this project.",
        )

    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **_: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("LLM API key is not configured")
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the DeepSeek API")

        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        if self._client is None:
            self._client = client

        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": self._system_prompt(analysis_type)},
                {"role": "user", "content": prompt},
            ],
        }

        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = ((data.get("choices") or [{}])[0]).get("message") or {}
        usage_data = data.get("usage") or {}
        return LLMResponse(
            content=choice.get("content", ""),
            model=data.get("model", self.model),
            usage=UsageInfo(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            raw_response=data,
        )

    async def web_search(
        self,
        query: str,
        *,
        max_results: int = 5,
        **_: Any,
    ) -> WebSearchResponse:
        raise NotImplementedError("DeepSeek client does not support native web search in this project")

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    def _system_prompt(self, analysis_type: str) -> str:
        prompts = {
            "fact_check": "You extract and verify factual claims from documents.",
            "quality": "You review document quality and return structured findings.",
            "structure": "You compare document structure against a template.",
            "general": "You analyze business documents and return structured output.",
        }
        return prompts.get(analysis_type, prompts["general"])
