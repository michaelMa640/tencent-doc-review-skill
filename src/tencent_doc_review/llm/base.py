"""Common LLM types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMCapabilities:
    provider: str = ""
    model: str = ""
    supports_structured_output: bool = True
    supports_native_web_search: bool = False
    native_web_search_strategy: str = ""
    notes: str = ""


@dataclass
class WebSearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""
    raw_content: str = ""
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "raw_content": self.raw_content,
            "score": self.score,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class WebSearchResponse:
    results: List[WebSearchResult] = field(default_factory=list)
    summary: str = ""
    provider: str = ""
    model: str = ""
    tool_type: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_result_dicts(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.results]


class LLMClient(Protocol):
    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        **kwargs: Any,
    ) -> LLMResponse:
        ...

    def get_capabilities(self) -> LLMCapabilities:
        ...

    async def web_search(
        self,
        query: str,
        *,
        max_results: int = 5,
        **kwargs: Any,
    ) -> WebSearchResponse:
        ...

    async def close(self) -> None:
        ...
