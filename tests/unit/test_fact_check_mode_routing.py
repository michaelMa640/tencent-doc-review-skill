import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import (
    Claim,
    ClaimType,
    FactChecker,
    NativeSearchClient,
    RoutedSearchClient,
    SearchClient,
)
from tencent_doc_review.llm.base import LLMCapabilities


def _build_llm_for_verification() -> Mock:
    llm_client = Mock()
    llm_client.analyze = AsyncMock(
        return_value=Mock(
            content='{"status":"confirmed","confidence":0.9,"evidence":[],"sources":[],"suggestion":"可保留。"}'
        )
    )
    return llm_client


class FactCheckModeRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_mode_prefers_native_web_search_when_supported(self):
        llm_client = _build_llm_for_verification()
        llm_client.get_capabilities = Mock(
            return_value=LLMCapabilities(
                provider="openai",
                model="gpt-5.4",
                supports_native_web_search=True,
                native_web_search_strategy="responses_api_web_search",
            )
        )
        llm_client.web_search = AsyncMock(
            return_value=Mock(
                model="gpt-5.4",
                tool_type="web_search",
                to_result_dicts=Mock(
                    return_value=[
                        {
                            "title": "官方文档",
                            "url": "https://example.com",
                            "snippet": "官方文档中提到了相关能力。",
                            "source": "example.com",
                        }
                    ]
                ),
            )
        )
        api_client = Mock(spec=SearchClient)
        api_client.enabled = True
        api_client.provider = "tavily"
        api_client.search = AsyncMock(return_value=[])
        api_client.verify_fact = AsyncMock(return_value={})
        api_client.close = AsyncMock()
        api_client._to_source_refs = SearchClient()._to_source_refs

        checker = FactChecker(
            llm_client=llm_client,
            search_client=RoutedSearchClient(
                mode="auto",
                native_client=NativeSearchClient(llm_client=llm_client),
                api_client=api_client,
            ),
        )
        claim = Claim(text="该产品支持 OpenAI 兼容接口。", claim_type=ClaimType.OTHER, needs_verification=True)

        result = await checker.verify_claim(claim, context={"document_title": "测试文档"})

        self.assertEqual(result.search_trace["mode"], "auto")
        self.assertEqual(result.search_trace["actual_mode"], "native")
        self.assertTrue(result.search_trace["performed"])
        self.assertEqual(result.search_trace["provider"], "openai")
        self.assertFalse(result.search_trace["fallback_triggered"])
        api_client.search.assert_not_awaited()

    async def test_auto_mode_falls_back_to_api_when_native_unavailable(self):
        llm_client = _build_llm_for_verification()
        llm_client.get_capabilities = Mock(
            return_value=LLMCapabilities(
                provider="openai",
                model="gpt-5.4",
                supports_native_web_search=False,
                native_web_search_strategy="",
            )
        )
        llm_client.web_search = AsyncMock()

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
            search_client=RoutedSearchClient(
                mode="auto",
                native_client=NativeSearchClient(llm_client=llm_client),
                api_client=api_client,
            ),
        )
        claim = Claim(text="该产品支持 OpenAI 兼容接口。", claim_type=ClaimType.OTHER, needs_verification=True)

        result = await checker.verify_claim(claim, context={"document_title": "测试文档"})

        self.assertEqual(result.search_trace["mode"], "auto")
        self.assertEqual(result.search_trace["actual_mode"], "api")
        self.assertTrue(result.search_trace["fallback_triggered"])
        self.assertEqual(result.search_trace["fallback_from"], "native")
        self.assertIn("当前审核模型未声明模型原生 web search 能力", result.search_trace["fallback_reason"])
        self.assertEqual(result.search_trace["provider"], "tavily")
        api_client.search.assert_awaited_once()
        llm_client.web_search.assert_not_awaited()

    async def test_offline_mode_skips_search(self):
        llm_client = _build_llm_for_verification()

        checker = FactChecker(
            llm_client=llm_client,
            search_client=RoutedSearchClient(mode="offline"),
        )
        claim = Claim(text="该产品发布于2025年。", claim_type=ClaimType.DATE_TIME, needs_verification=True)

        result = await checker.verify_claim(claim)

        self.assertEqual(
            result.search_trace,
            {
                "performed": False,
                "provider": "offline",
                "raw_count": 0,
                "filtered_count": 0,
                "mode": "offline",
                "actual_mode": "offline",
            },
        )

    async def test_auto_mode_without_native_or_api_reports_reason(self):
        llm_client = _build_llm_for_verification()
        llm_client.get_capabilities = Mock(
            return_value=LLMCapabilities(
                provider="openai",
                model="gpt-5.4",
                supports_native_web_search=False,
                native_web_search_strategy="",
            )
        )
        llm_client.web_search = AsyncMock()

        checker = FactChecker(
            llm_client=llm_client,
            search_client=RoutedSearchClient(
                mode="auto",
                native_client=NativeSearchClient(llm_client=llm_client),
            ),
        )
        claim = Claim(text="该产品发布于2025年。", claim_type=ClaimType.DATE_TIME, needs_verification=True)

        result = await checker.verify_claim(claim)

        self.assertFalse(result.search_trace["performed"])
        self.assertEqual(result.search_trace["mode"], "auto")
        self.assertEqual(result.search_trace["llm_provider"], "openai")
        self.assertEqual(result.search_trace["llm_model"], "gpt-5.4")
        self.assertIn("模型原生 web search 不可用", result.search_trace["reason"])
        self.assertIn("Tavily API 未配置", result.search_trace["reason"])

    async def test_native_mode_does_not_fallback_to_api(self):
        llm_client = _build_llm_for_verification()
        llm_client.get_capabilities = Mock(
            return_value=LLMCapabilities(
                provider="openai",
                model="gpt-5.4",
                supports_native_web_search=False,
                native_web_search_strategy="",
            )
        )
        llm_client.web_search = AsyncMock()
        api_client = Mock(spec=SearchClient)
        api_client.enabled = True
        api_client.provider = "tavily"
        api_client.search = AsyncMock(return_value=[])
        api_client.verify_fact = AsyncMock(return_value={})
        api_client.close = AsyncMock()
        api_client._to_source_refs = SearchClient()._to_source_refs

        checker = FactChecker(
            llm_client=llm_client,
            search_client=RoutedSearchClient(
                mode="native",
                native_client=NativeSearchClient(llm_client=llm_client),
                api_client=api_client,
            ),
        )
        claim = Claim(text="该产品发布于2025年。", claim_type=ClaimType.DATE_TIME, needs_verification=True)

        result = await checker.verify_claim(claim)

        self.assertFalse(result.search_trace["performed"])
        self.assertEqual(result.search_trace["mode"], "native")
        self.assertEqual(result.search_trace["actual_mode"], "native")
        self.assertIn("当前审核模型未声明模型原生 web search 能力", result.search_trace["reason"])
        api_client.search.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
