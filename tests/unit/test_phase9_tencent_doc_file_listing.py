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
from tencent_doc_review.tencent_doc_client import DocumentInfo, TencentDocClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)

    async def request(self, method, url, headers=None, json=None, params=None):
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def aclose(self):
        return None


class _FakeListingClient:
    async def convert_encoded_id_to_file_id(self, encoded_id: str):
        return "300000000$AAAAAAAAAAAA"

    async def debug_converter_response(self, encoded_id: str):
        return {
            "encoded_id": encoded_id,
            "summary": {"ret": 0, "msg": "Succeed", "data": {"fileID": "300000000$AAAAAAAAAAAA"}},
            "error_fields": {"ret": 0, "msg": "Succeed", "code": None, "message": None},
            "data_keys": ["fileID"],
        }

    async def list_documents(self, folder_id: str):
        return [
            DocumentInfo(file_id="300000000$AAAAAAAAAAAA", title="示例文档", doc_type="doc"),
            DocumentInfo(file_id="300000000$BBBBBBBBBBBB", title="示例表格", doc_type="sheet"),
        ]

    async def close(self):
        return None


class Phase9TencentDocFileListingTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_can_convert_encoded_id(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(200, {"ret": 0, "msg": "Succeed", "data": {"fileID": "300000000$AAAAAAAAAAAA"}}),
            ]
        )
        client = TencentDocClient(
            access_token="token",
            client_id="client",
            open_id="open",
            client=fake_client,
        )

        file_id = await client.convert_encoded_id_to_file_id("DFFFFFFFFFFFFFFFF")

        self.assertEqual(file_id, "300000000$AAAAAAAAAAAA")

    async def test_client_converter_error_contains_ret_and_message(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(200, {"ret": 10301, "msg": "Permission denied", "data": {}}),
            ]
        )
        client = TencentDocClient(
            access_token="token",
            client_id="client",
            open_id="open",
            client=fake_client,
        )

        with self.assertRaisesRegex(
            Exception,
            r"ret=10301, msg=Permission denied, code=None, message=None",
        ):
            await client.convert_encoded_id_to_file_id("DFFFFFFFFFFFFFFFF")

    async def test_client_can_list_folder_documents(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(
                    200,
                    {
                        "ret": 0,
                        "msg": "Succeed",
                        "data": {
                            "files": [
                                {"fileID": "300000000$AAAAAAAAAAAA", "title": "示例文档", "type": "doc"},
                                {"fileID": "300000000$BBBBBBBBBBBB", "title": "示例表格", "type": "sheet"},
                            ]
                        },
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

        items = await client.list_documents("folder-123")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].file_id, "300000000$AAAAAAAAAAAA")
        self.assertEqual(items[0].title, "示例文档")

    def test_cli_list_files_can_resolve_encoded_id(self):
        runner = CliRunner()
        fake_client = _FakeListingClient()
        with patch("tencent_doc_review.cli._create_tencent_doc_client", return_value=fake_client):
            result = runner.invoke(
                main,
                [
                    "list-files",
                    "--encoded-id",
                    "DFFFFFFFFFFFFFFFF",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["file_id"], "300000000$AAAAAAAAAAAA")
        self.assertIn("analyze --doc-id", payload["analyze_command"])

    def test_cli_list_files_can_print_table(self):
        runner = CliRunner()
        fake_client = _FakeListingClient()
        with patch("tencent_doc_review.cli._create_tencent_doc_client", return_value=fake_client):
            result = runner.invoke(
                main,
                [
                    "list-files",
                    "--folder-id",
                    "folder-123",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("file_id\ttype\ttitle", result.output)
        self.assertIn("300000000$AAAAAAAAAAAA", result.output)

    def test_cli_debug_converter_prints_summary(self):
        runner = CliRunner()
        fake_client = _FakeListingClient()
        with patch("tencent_doc_review.cli._create_tencent_doc_client", return_value=fake_client):
            result = runner.invoke(
                main,
                [
                    "debug-converter",
                    "--encoded-id",
                    "DFFFFFFFFFFFFFFFF",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn('"encoded_id": "DFFFFFFFFFFFFFFFF"', result.output)
        self.assertIn('"fileID"', result.output)


if __name__ == "__main__":
    unittest.main()
