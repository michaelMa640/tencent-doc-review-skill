import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
TMP_ROOT = PROJECT_ROOT / "tests" / ".tmp"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.cli import main
from tencent_doc_review.llm.factory import create_llm_client


class Phase2CliFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def test_factory_supports_mock_provider(self):
        client = create_llm_client(provider="mock")
        self.assertEqual(type(client).__name__, "MockLLMClient")

    def test_cli_analyze_generates_markdown_report(self):
        runner = CliRunner()
        tmpdir = TMP_ROOT / f"phase2-md-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            input_path = tmpdir / "input.md"
            template_path = tmpdir / "template.md"
            output_path = tmpdir / "report.md"

            input_path.write_text("# 示例文章\n\n## 背景\n内容。\n\n## 结论\n结论。", encoding="utf-8")
            template_path.write_text("# 模板\n\n## 背景\n## 分析\n## 结论", encoding="utf-8")

            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--input-file",
                    str(input_path),
                    "--template-file",
                    str(template_path),
                    "--output",
                    str(output_path),
                    "--format",
                    "markdown",
                    "--provider",
                    "mock",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Document Review Report", content)
            self.assertIn("Recommendations", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_analyze_generates_json_report(self):
        runner = CliRunner()
        tmpdir = TMP_ROOT / f"phase2-json-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            input_path = tmpdir / "input.md"
            output_path = tmpdir / "report.json"

            input_path.write_text("# 示例文章\n\n测试内容。", encoding="utf-8")

            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--input-file",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--format",
                    "json",
                    "--provider",
                    "mock",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(output_path.exists())
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("summary", data)
            self.assertIn("recommendations", data)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_analyze_supports_default_template_flag(self):
        runner = CliRunner()
        tmpdir = TMP_ROOT / f"phase2-default-template-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            input_path = tmpdir / "input.md"
            output_path = tmpdir / "report.md"

            input_path.write_text("# 示例文章\n\n## 产品概述\n内容。\n", encoding="utf-8")

            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--input-file",
                    str(input_path),
                    "--default-template",
                    "--output",
                    str(output_path),
                    "--format",
                    "markdown",
                    "--provider",
                    "mock",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(output_path.exists())
            self.assertIn("Template: built-in default", result.output)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Structure Match", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
