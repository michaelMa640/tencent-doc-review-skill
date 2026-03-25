import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.cli import main
from tencent_doc_review.tencent_doc_client import (
    DocumentInfo,
    TencentDocClient,
    TencentDocRateLimitError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def request(self, method, url, headers=None, json=None):
        self.calls += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def aclose(self):
        return None


class _FakeTencentDocClient:
    async def get_document_bundle(self, file_id: str):
        return DocumentInfo(file_id=file_id, title="Tencent Doc Sample"), "# 腾讯文档\n\n测试内容。"

    async def get_document_content(self, file_id: str):
        return "# 模板\n\n## 背景\n## 结论"

    async def add_comments_batch(self, file_id, comments):
        return {"success": False}

    async def close(self):
        return None


class Phase6TencentDocInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_reads_metadata_and_content(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(
                    200,
                    {"file": {"title": "Doc Title", "type": "doc", "url": "https://docs.qq.com/test"}},
                ),
                _FakeResponse(
                    200,
                    {
                        "document": {
                            "type": "Paragraph",
                            "children": [
                                {"text": "Hello "},
                                {"text": "Tencent Docs"},
                            ],
                        }
                    },
                ),
            ]
        )
        client = TencentDocClient(
            access_token="token",
            client_id="client",
            open_id="open",
            client=fake_client,
        )

        info, content = await client.get_document_bundle("doc-123")

        self.assertEqual(info.title, "Doc Title")
        self.assertIn("Tencent Docs", content)

    async def test_client_retries_rate_limit(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(429, {}),
                _FakeResponse(200, {"document": {"text": "Recovered"}}),
            ]
        )
        client = TencentDocClient(
            access_token="token",
            client_id="client",
            open_id="open",
            client=fake_client,
            max_retries=1,
            retry_delay=0,
        )

        content = await client.get_document_content("doc-123")

        self.assertEqual(content, "Recovered")
        self.assertEqual(fake_client.calls, 2)

    async def test_client_raises_after_retry_exhausted(self):
        fake_client = _FakeAsyncClient([_FakeResponse(429, {}), _FakeResponse(429, {})])
        client = TencentDocClient(
            access_token="token",
            client_id="client",
            open_id="open",
            client=fake_client,
            max_retries=1,
            retry_delay=0,
        )

        with self.assertRaises(TencentDocRateLimitError):
            await client.get_document_content("doc-123")

    def test_cli_analyze_supports_doc_id_input(self):
        runner = CliRunner()
        with patch("tencent_doc_review.cli._create_tencent_doc_client", return_value=_FakeTencentDocClient()):
            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--doc-id",
                    "doc-123",
                    "--template-doc-id",
                    "tpl-456",
                    "--format",
                    "json",
                    "--provider",
                    "mock",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["document_id"], "doc-123")
        self.assertEqual(payload["document_title"], "Tencent Doc Sample")


if __name__ == "__main__":
    unittest.main()
