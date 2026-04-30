import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.llm.providers.openai import OpenAIClient


class OpenAINativeWebSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_openai_client_reports_native_web_search_capability(self):
        client = OpenAIClient(api_key="test-key", model="gpt-5.4")

        capabilities = client.get_capabilities()

        self.assertEqual(capabilities.provider, "openai")
        self.assertEqual(capabilities.model, "gpt-5.4")
        self.assertTrue(capabilities.supports_native_web_search)
        self.assertEqual(capabilities.native_web_search_strategy, "responses_api_web_search")

    async def test_web_search_uses_responses_api_and_parses_sources(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(
            return_value={
                "model": "gpt-5.4",
                "output_text": "OpenAI launched a new capability for developers.",
                "output": [
                    {
                        "type": "web_search_call",
                        "action": {
                            "sources": [
                                {
                                    "title": "Platform Docs",
                                    "url": "https://platform.openai.com/docs",
                                    "snippet": "Official documentation for developers.",
                                }
                            ]
                        },
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "OpenAI launched a new capability for developers.",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "title": "OpenAI News",
                                        "url": "https://openai.com/news",
                                        "start_index": 0,
                                        "end_index": 21,
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        )
        http_client = Mock()
        http_client.post = AsyncMock(return_value=response)
        client = OpenAIClient(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="gpt-5.4",
            client=http_client,
        )

        result = await client.web_search("OpenAI latest capability", max_results=5)

        http_client.post.assert_awaited_once()
        _, kwargs = http_client.post.await_args
        self.assertEqual(kwargs["json"]["model"], "gpt-5.4")
        self.assertEqual(kwargs["json"]["tools"][0]["type"], "web_search")
        self.assertEqual(kwargs["json"]["input"], "OpenAI latest capability")
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "gpt-5.4")
        self.assertEqual(result.tool_type, "web_search")
        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.results[0].title, "OpenAI News")
        self.assertEqual(result.results[0].url, "https://openai.com/news")
        self.assertEqual(result.results[0].snippet, "OpenAI launched a new")
        self.assertEqual(result.results[1].title, "Platform Docs")
        self.assertEqual(result.results[1].snippet, "Official documentation for developers.")

    async def test_web_search_retries_with_preview_tool_when_gateway_rejects_web_search(self):
        failing_response = Mock()
        failing_response.raise_for_status = Mock(side_effect=RuntimeError("Unknown tool type: web_search"))
        passing_response = Mock()
        passing_response.raise_for_status = Mock()
        passing_response.json = Mock(
            return_value={
                "model": "gpt-5.4",
                "output_text": "Fallback search succeeded.",
                "output": [],
            }
        )
        http_client = Mock()
        http_client.post = AsyncMock(side_effect=[failing_response, passing_response])
        client = OpenAIClient(api_key="test-key", client=http_client, model="gpt-5.4")

        result = await client.web_search("fallback query")

        self.assertEqual(http_client.post.await_count, 2)
        first_call = http_client.post.await_args_list[0]
        second_call = http_client.post.await_args_list[1]
        self.assertEqual(first_call.kwargs["json"]["tools"][0]["type"], "web_search")
        self.assertEqual(second_call.kwargs["json"]["tools"][0]["type"], "web_search_preview")
        self.assertEqual(result.tool_type, "web_search_preview")
        self.assertEqual(result.summary, "Fallback search succeeded.")


if __name__ == "__main__":
    unittest.main()
