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


if __name__ == "__main__":
    unittest.main()
