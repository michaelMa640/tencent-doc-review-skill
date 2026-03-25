"""Mock provider for local end-to-end verification."""

from __future__ import annotations

from typing import Any

from ..base import LLMResponse, UsageInfo


class MockLLMClient:
    """Deterministic provider used for local CLI verification."""

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

    async def close(self) -> None:
        return None
