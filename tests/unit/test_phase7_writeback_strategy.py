import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.document_analyzer import DocumentAnalyzer
from tencent_doc_review.llm.providers.mock import MockLLMClient
from tencent_doc_review.writers import DocAppendWriter, NoopAnnotationAdapter, ReportGenerator


class _FakeWritebackClient:
    def __init__(self) -> None:
        self.append_calls = []

    async def get_document_bundle(self, file_id: str):
        from tencent_doc_review.tencent_doc_client import DocumentInfo

        return DocumentInfo(file_id=file_id, title="Doc For Writeback"), "# Existing Content\n"

    async def get_document_content(self, file_id: str):
        return "# Template\n\n## 背景\n## 结论"

    async def append_review_block(self, file_id: str, block_markdown: str):
        self.append_calls.append((file_id, block_markdown))
        return {"success": True, "mode": "append", "file_id": file_id}

    async def add_comments_batch(self, file_id, comments):
        return {"success": False}

    async def close(self):
        return None


class Phase7WritebackStrategyTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_generator_supports_html(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(document_text="# 示例\n\n内容", document_title="示例")

        html = ReportGenerator().render(result, "html")

        self.assertIn("<html>", html)
        self.assertIn("Document Review Report", html)

    async def test_doc_append_writer_renders_fixed_block(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(document_text="# 示例\n\n内容", document_title="示例")

        block = DocAppendWriter().render_block(result)

        self.assertIn("## AI 审核建议", block)
        self.assertIn("### 摘要", block)
        self.assertIn("### 建议", block)

    async def test_doc_append_writer_calls_client_append(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(document_text="# 示例\n\n内容", document_title="示例")
        client = _FakeWritebackClient()

        writeback = await DocAppendWriter().write(client, "doc-123", result)

        self.assertTrue(writeback["success"])
        self.assertEqual(writeback["mode"], "append")
        self.assertEqual(client.append_calls[0][0], "doc-123")

    async def test_noop_annotation_adapter_stays_explicit(self):
        result = await NoopAnnotationAdapter().write_annotations("doc-123", [])

        self.assertFalse(result["success"])
        self.assertEqual(result["mode"], "noop")

    def test_cli_supports_append_writeback_mode(self):
        from tencent_doc_review.cli import main

        runner = CliRunner()
        fake_client = _FakeWritebackClient()
        with patch("tencent_doc_review.cli._create_tencent_doc_client", return_value=fake_client):
            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--doc-id",
                    "doc-123",
                    "--writeback-mode",
                    "append",
                    "--provider",
                    "mock",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Writeback mode: append", result.output)
        self.assertEqual(len(fake_client.append_calls), 1)


if __name__ == "__main__":
    unittest.main()
