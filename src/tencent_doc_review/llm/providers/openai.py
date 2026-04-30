"""OpenAI-compatible provider with optional native web search support."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback for lean environments
    httpx = None

from ..base import LLMCapabilities, LLMResponse, UsageInfo, WebSearchResponse, WebSearchResult


class OpenAIClient:
    """Async wrapper for OpenAI-compatible APIs, including native web search."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4.1-mini",
        timeout: int = 30,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    def get_capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            provider="openai",
            model=self.model,
            supports_native_web_search=True,
            native_web_search_strategy="responses_api_web_search",
            notes=(
                "Uses the Responses API with web_search/web_search_preview tools. "
                "Runtime support still depends on the configured OpenAI-compatible gateway."
            ),
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
            raise ModuleNotFoundError("httpx is required to call the OpenAI API")

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
        search_context_size: str = "medium",
        user_location: Optional[Dict[str, str]] = None,
        max_output_tokens: int = 1024,
        **_: Any,
    ) -> WebSearchResponse:
        if not self.api_key:
            raise ValueError("LLM API key is not configured")
        if httpx is None:
            raise ModuleNotFoundError("httpx is required to call the OpenAI API")
        if not query or not query.strip():
            return WebSearchResponse(provider="openai", model=self.model)

        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        if self._client is None:
            self._client = client

        last_error: Optional[Exception] = None
        for tool_type in ("web_search", "web_search_preview"):
            payload = self._build_web_search_payload(
                query=query,
                tool_type=tool_type,
                search_context_size=search_context_size,
                user_location=user_location,
                max_output_tokens=max_output_tokens,
            )
            try:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_web_search_response(
                    data,
                    tool_type=tool_type,
                    max_results=max_results,
                )
            except Exception as exc:
                last_error = exc
                if not self._should_retry_with_preview(exc, tool_type):
                    raise

        assert last_error is not None
        raise last_error

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

    def _build_web_search_payload(
        self,
        *,
        query: str,
        tool_type: str,
        search_context_size: str,
        user_location: Optional[Dict[str, str]],
        max_output_tokens: int,
    ) -> Dict[str, Any]:
        tool: Dict[str, Any] = {
            "type": tool_type,
            "search_context_size": search_context_size,
        }
        if user_location:
            tool["user_location"] = user_location
        return {
            "model": self.model,
            "input": query,
            "tools": [tool],
            "tool_choice": "auto",
            "max_output_tokens": max_output_tokens,
        }

    def _parse_web_search_response(
        self,
        data: Dict[str, Any],
        *,
        tool_type: str,
        max_results: int,
    ) -> WebSearchResponse:
        output_text = self._extract_output_text(data)
        results = self._extract_web_search_results(data, output_text)[:max_results]
        return WebSearchResponse(
            results=results,
            summary=output_text,
            provider="openai",
            model=str(data.get("model") or self.model),
            tool_type=tool_type,
            raw_response=data,
        )

    def _extract_output_text(self, data: Dict[str, Any]) -> str:
        direct_text = str(data.get("output_text") or "").strip()
        if direct_text:
            return direct_text

        parts: List[str] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text_value = str(content.get("text") or content.get("content") or "").strip()
                if text_value:
                    parts.append(text_value)
        return "\n".join(part for part in parts if part).strip()

    def _extract_web_search_results(
        self,
        data: Dict[str, Any],
        output_text: str,
    ) -> List[WebSearchResult]:
        indexed: Dict[str, WebSearchResult] = {}

        for annotation in self._iter_url_citations(data):
            url = str(annotation.get("url") or "").strip()
            if not url:
                continue
            title = str(annotation.get("title") or url).strip()
            snippet = self._extract_annotation_snippet(annotation, output_text)
            indexed[url] = WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=urlparse(url).netloc,
                raw_content=snippet,
                metadata={"annotation_type": str(annotation.get("type") or "url_citation")},
            )

        for source in self._iter_action_sources(data):
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            existing = indexed.get(url)
            title = str(source.get("title") or (existing.title if existing else "") or url).strip()
            snippet = str(source.get("snippet") or (existing.snippet if existing else "")).strip()
            indexed[url] = WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=urlparse(url).netloc,
                raw_content=str(source.get("raw_content") or snippet).strip(),
                metadata={"source_type": "action_source"},
            )

        return list(indexed.values())

    def _iter_url_citations(self, data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                for annotation in content.get("annotations") or []:
                    if not isinstance(annotation, dict):
                        continue
                    annotation_type = str(annotation.get("type") or "").strip().lower()
                    if annotation_type in {"url_citation", "citation"}:
                        yield annotation

    def _iter_action_sources(self, data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").strip().lower() != "web_search_call":
                continue
            action = item.get("action") or {}
            for source in action.get("sources") or []:
                if isinstance(source, dict):
                    yield source

    def _extract_annotation_snippet(self, annotation: Dict[str, Any], output_text: str) -> str:
        if not output_text:
            return ""
        start_index = annotation.get("start_index")
        end_index = annotation.get("end_index")
        if isinstance(start_index, int) and isinstance(end_index, int) and 0 <= start_index < end_index <= len(output_text):
            return output_text[start_index:end_index].strip()
        return ""

    def _should_retry_with_preview(self, exc: Exception, tool_type: str) -> bool:
        if tool_type != "web_search":
            return False
        message = str(exc).lower()
        return "web_search" in message and any(
            token in message
            for token in ("unknown", "unsupported", "invalid", "not support", "not found", "unrecognized")
        )
