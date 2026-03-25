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


class Phase8ReleaseDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def test_cli_analyze_generates_html_report(self):
        runner = CliRunner()
        tmpdir = TMP_ROOT / f"phase8-html-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            input_path = tmpdir / "input.md"
            output_path = tmpdir / "report.html"

            input_path.write_text("# 示例文档\n\n这是一个用于发布验证的测试输入。", encoding="utf-8")

            result = runner.invoke(
                main,
                [
                    "analyze",
                    "--input-file",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--format",
                    "html",
                    "--provider",
                    "mock",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("<html>", content)
            self.assertIn("Document Review Report", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
