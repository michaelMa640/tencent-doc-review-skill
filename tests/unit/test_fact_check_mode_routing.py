import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import Claim, ClaimType, FactChecker, RoutedSearchClient, SearchClient


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_api_when_agent_unavailable():
    llm_client = Mock()
    llm_client.analyze = AsyncMock(
        return_value=Mock(
            content='{"status":"confirmed","confidence":0.9,"evidence":[],"sources":[],"suggestion":"可保留。"}'
        )
    )

    api_client = Mock(spec=SearchClient)
    api_client.enabled = True
    api_client.provider = "tavily"
    api_client.search = AsyncMock(
        return_value=[
            {
                "title": "官方文档",
                "url": "https://example.com",
                "snippet": "官方文档中提到了相关能力。",
                "source": "example.com",
            }
        ]
    )
    api_client.verify_fact = AsyncMock(return_value={})
    api_client.close = AsyncMock()
    api_client._to_source_refs = SearchClient()._to_source_refs

    checker = FactChecker(
        llm_client=llm_client,
        search_client=RoutedSearchClient(mode="auto", api_client=api_client),
    )
    claim = Claim(text="该产品支持 OpenAI 兼容接口。", claim_type=ClaimType.OTHER, needs_verification=True)

    result = await checker.verify_claim(claim, context={"document_title": "测试文档"})

    assert result.search_trace["mode"] == "auto"
    assert result.search_trace["actual_mode"] == "api"
    assert result.search_trace["fallback_triggered"] is True
    assert result.search_trace["fallback_from"] == "agent"


@pytest.mark.asyncio
async def test_offline_mode_skips_search():
    llm_client = Mock()
    llm_client.analyze = AsyncMock(
        return_value=Mock(
            content='{"status":"unverified","confidence":0.2,"evidence":[],"sources":[],"suggestion":"待核查。"}'
        )
    )

    checker = FactChecker(
        llm_client=llm_client,
        search_client=RoutedSearchClient(mode="offline"),
    )
    claim = Claim(text="该产品发布于2025年。", claim_type=ClaimType.DATE_TIME, needs_verification=True)

    result = await checker.verify_claim(claim)

    assert result.search_trace == {"performed": False, "provider": "offline", "raw_count": 0, "filtered_count": 0}
