import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import SearchClient


class SearchClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_tavily_search_maps_results(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(
            return_value={
                "results": [
                    {
                        "title": "MiniMax Pricing",
                        "url": "https://example.com/pricing",
                        "content": "MiniMax publishes pricing details on its official page.",
                        "score": 0.92,
                    }
                ]
            }
        )
        http_client = Mock()
        http_client.post = AsyncMock(return_value=response)

        client = SearchClient(
            api_key="search-key",
            provider="tavily",
            client=http_client,
        )

        results = await client.search("MiniMax pricing", num_results=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "MiniMax Pricing")
        self.assertEqual(results[0]["url"], "https://example.com/pricing")
        self.assertIn("official page", results[0]["snippet"])
        http_client.post.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
