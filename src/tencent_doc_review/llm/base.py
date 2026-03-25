"""Common LLM types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol


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


class LLMClient(Protocol):
    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        **kwargs: Any,
    ) -> LLMResponse:
        ...

    async def close(self) -> None:
        ...
