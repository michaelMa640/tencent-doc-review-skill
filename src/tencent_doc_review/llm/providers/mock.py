"""Mock provider for local end-to-end verification."""

from __future__ import annotations

from typing import Any

from ..base import LLMCapabilities, LLMResponse, UsageInfo, WebSearchResponse


class MockLLMClient:
    """Deterministic provider used for local CLI verification."""

    def get_capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            provider="mock",
            model="mock",
            supports_native_web_search=False,
            notes="Mock provider does not execute live web search.",
        )

    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        **_: Any,
    ) -> LLMResponse:
        responses = {
            "fact_check": """{
  "claims": [
    {
      "text": "示例数据需要进一步核实",
      "type": "data",
      "claim": "示例数据需要进一步核实",
      "entities": [],
      "context": "mock output"
    }
  ]
}""",
            "quality": """{
  "score": 82,
  "level": "good",
  "strengths": ["结构清晰", "表达基本完整"],
  "weaknesses": ["论据较少"],
  "suggestions": ["补充更多可验证的数据或案例"]
}""",
            "general": '{"status":"ok"}',
            "structure": '{"status":"ok"}',
        }
        return LLMResponse(
            content=responses.get(analysis_type, responses["general"]),
            model="mock",
            usage=UsageInfo(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            raw_response={},
        )

    async def web_search(
        self,
        query: str,
        *,
        max_results: int = 5,
        **_: Any,
    ) -> WebSearchResponse:
        raise NotImplementedError("Mock provider does not support native web search")

    async def close(self) -> None:
        return None
