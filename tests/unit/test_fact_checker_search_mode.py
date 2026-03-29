import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import FactChecker, SearchClient, VerificationStatus


class FactCheckerSearchModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_fact_checker_prefers_search_backed_verification(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            side_effect=[
                Mock(
                    content=(
                        '[{"text":"MiniMax M2.7 supports an OpenAI-compatible API",'
                        '"claim_type":"other","confidence":0.8,"needs_verification":true}]'
                    )
                ),
                Mock(
                    content=(
                        '{"status":"confirmed","confidence":0.9,'
                        '"evidence":["Official docs mention OpenAI-compatible endpoints."],'
                        '"sources":[{"title":"MiniMax Docs","url":"https://platform.minimaxi.com/docs"}],'
                        '"suggestion":"可保留该表述。"}'
                    )
                ),
            ]
        )

        search_client = Mock(spec=SearchClient)
        search_client.enabled = True
        search_client.provider = "tavily"
        search_client.search = AsyncMock(
            return_value=[
                {
                    "title": "MiniMax Docs",
                    "url": "https://platform.minimaxi.com/docs",
                    "snippet": "MiniMax provides an OpenAI-compatible text API.",
                    "source": "platform.minimaxi.com",
                }
            ]
        )
        search_client.verify_fact = AsyncMock(
            return_value={
                "status": "unverified",
                "confidence": 0.35,
                "evidence": [],
                "sources": [],
                "suggestion": "该内容需要复查。",
            }
        )
        search_client.close = AsyncMock()

        checker = FactChecker(llm_client=llm_client, search_client=search_client)
        results = await checker.check("MiniMax M2.7 supports an OpenAI-compatible API.")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].verification_status, VerificationStatus.CONFIRMED)
        self.assertEqual(results[0].sources[0]["url"], "https://platform.minimaxi.com/docs")
        search_client.search.assert_awaited_once()

    async def test_fact_checker_filters_irrelevant_search_results(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            side_effect=[
                Mock(
                    content=(
                        '[{"text":"生成的视频清晰度可达4K。",'
                        '"claim_type":"data","confidence":0.8,"needs_verification":true}]'
                    )
                ),
                Mock(
                    content=(
                        '{"status":"unverified","confidence":0.6,'
                        '"evidence":[],"sources":[],"suggestion":"检索到的公开信息未能直接证实该表述，建议依据下列来源核对后再保留。"}'
                    )
                ),
            ]
        )

        search_client = Mock(spec=SearchClient)
        search_client.enabled = True
        search_client.provider = "tavily"
        search_client.search = AsyncMock(
            return_value=[
                {
                    "title": "cnBeta.COM中文业界资讯站",
                    "url": "https://t.me/s/cnbeta_com?before=443550",
                    "snippet": "无关内容",
                    "source": "t.me",
                    "score": 0.95,
                },
                {
                    "title": "蝉镜数字人帮助文档",
                    "url": "https://www.chanjing.cc/docs/ai-digital-human-guide/366.html",
                    "snippet": "蝉镜数字人支持快速生成数字人视频。",
                    "source": "www.chanjing.cc",
                    "score": 0.82,
                },
            ]
        )
        search_client.verify_fact = AsyncMock(return_value={})
        search_client.close = AsyncMock()
        search_client._to_source_refs = SearchClient()._to_source_refs

        checker = FactChecker(
            llm_client=llm_client,
            search_client=search_client,
            config={"search_max_results": 5},
        )
        results = await checker.check(
            "生成的视频清晰度可达4K。",
            context={"document_title": "副本-蝉镜产品调研报告-michael", "product_name": "蝉镜"},
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].sources), 1)
        self.assertIn("chanjing.cc", results[0].sources[0]["url"])
        self.assertNotIn("t.me", results[0].sources[0]["url"])

    async def test_fact_checker_drops_sources_when_all_candidates_are_irrelevant(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            side_effect=[
                Mock(
                    content=(
                        '[{"text":"生成的视频清晰度可达4K。",'
                        '"claim_type":"data","confidence":0.8,"needs_verification":true}]'
                    )
                ),
                Mock(
                    content=(
                        '{"status":"unverified","confidence":0.6,'
                        '"evidence":[],"sources":[],"suggestion":"检索到的公开信息未能直接证实该表述，建议依据下列来源核对后再保留。"}'
                    )
                ),
            ]
        )

        search_client = Mock(spec=SearchClient)
        search_client.enabled = True
        search_client.provider = "tavily"
        search_client.search = AsyncMock(
            return_value=[
                {
                    "title": "Quantum Vault Trading Center Video Reviews Projects",
                    "url": "https://www.behance.net/search/projects/Quantum%20Vault%20Trading%20Center%20Video%20Reviews",
                    "snippet": "无关内容",
                    "source": "www.behance.net",
                    "score": 0.96,
                }
            ]
        )
        search_client.verify_fact = AsyncMock(return_value={})
        search_client.close = AsyncMock()
        search_client._to_source_refs = SearchClient()._to_source_refs

        checker = FactChecker(
            llm_client=llm_client,
            search_client=search_client,
            config={"search_max_results": 5},
        )
        results = await checker.check(
            "生成的视频清晰度可达4K。",
            context={"document_title": "副本-蝉镜产品调研报告-michael", "product_name": "蝉镜"},
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sources, [])


if __name__ == "__main__":
    unittest.main()
