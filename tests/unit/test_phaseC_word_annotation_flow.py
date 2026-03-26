import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path

from docx import Document

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.document import WordAnnotation, WordAnnotator, WordParser


class PhaseCWordAnnotationFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = PROJECT_ROOT / "tests" / ".tmp" / f"phasec-word-{uuid.uuid4().hex}"
        self.tmpdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_sample_docx(self) -> Path:
        source_path = self.tmpdir / "source.docx"
        document = Document()
        document.add_heading("示例文档", level=1)
        document.add_paragraph("第一段内容。")
        document.add_paragraph("第二段内容。")
        document.save(source_path)
        return source_path

    def test_word_parser_extracts_paragraphs_and_headings(self):
        source_path = self._create_sample_docx()

        parsed = WordParser().parse(source_path)

        self.assertEqual(parsed.title, "示例文档")
        self.assertEqual(len(parsed.paragraphs), 3)
        self.assertTrue(parsed.paragraphs[0].is_heading)
        self.assertEqual(parsed.paragraphs[1].text, "第一段内容。")

    def test_word_annotator_exports_native_comments(self):
        source_path = self._create_sample_docx()
        output_path = self.tmpdir / "annotated.docx"

        result = WordAnnotator().annotate(
            source_path=source_path,
            output_path=output_path,
            document_title="示例文档",
            annotations=[
                WordAnnotation(
                    paragraph_index=1,
                    title="事实核查提示",
                    comment="这里需要补充数据来源。",
                    severity="high",
                    source_excerpt="第一段内容。",
                ),
                WordAnnotation(
                    paragraph_index=2,
                    title="结构建议",
                    comment="建议增加结论段。",
                    severity="medium",
                    source_excerpt="第二段内容。",
                ),
            ],
        )

        self.assertTrue(output_path.exists())
        self.assertEqual(result.annotation_count, 2)
        self.assertEqual(result.metadata["comment_mode"], "native")

        rendered = Document(output_path)
        self.assertEqual(len(rendered.comments), 2)
        self.assertIn("AI Review", [comment.author for comment in rendered.comments])
        self.assertTrue(any("这里需要补充数据来源。" in comment.text for comment in rendered.comments))

        with zipfile.ZipFile(output_path) as package:
            names = set(package.namelist())
            self.assertIn("word/comments.xml", names)


if __name__ == "__main__":
    unittest.main()
