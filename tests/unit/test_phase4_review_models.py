import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.document_analyzer import DocumentAnalyzer
from tencent_doc_review.domain import ReviewIssueType, ReviewSeverity
from tencent_doc_review.llm.providers.mock import MockLLMClient


class Phase4ReviewModelsTests(unittest.IsolatedAsyncioTestCase):
    async def test_analysis_result_exposes_unified_review_report(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(
            document_text="# 示例文章\n\n## 背景\n内容。\n\n## 结论\n结论。",
            template_text="# 模板\n\n## 背景\n## 分析\n## 结论",
            document_title="示例文章",
        )

        self.assertIsNotNone(result.review_report)
        self.assertIsInstance(result.review_issues, list)
        self.assertGreater(len(result.review_issues), 0)
        self.assertIn("issue_count", result.review_report.metrics)
        self.assertEqual(result.review_report.metrics["issue_count"], len(result.review_issues))
        structure_issues = [item for item in result.review_issues if item.issue_type == ReviewIssueType.STRUCTURE]
        self.assertEqual(len(structure_issues), 1)
        self.assertIn("分析", structure_issues[0].description)
        self.assertIn("补充“分析”部分的内容", structure_issues[0].suggestion)
        markdown = result.to_markdown()
        self.assertIn("## Structure Issues", markdown)
        self.assertIn("当前与模板相比仍缺少这些部分", markdown)
        self.assertIn("请补齐这些缺失章节：分析。", markdown)

    async def test_unified_review_serialization_is_stable(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(
            document_text="# 示例文章\n\n测试内容。",
            document_title="示例文章",
        )

        payload = result.to_dict()
        self.assertIn("review_issues", payload)
        self.assertIn("review_report", payload)
        self.assertIsInstance(payload["review_issues"], list)
        self.assertIsInstance(payload["review_report"], dict)
        json.loads(json.dumps(payload, ensure_ascii=False))

    async def test_unified_issues_have_consistent_shape(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        result = await analyzer.analyze(
            document_text="# 示例文章\n\n测试内容。",
            document_title="示例文章",
        )

        first_issue = result.review_issues[0]
        self.assertIn(first_issue.issue_type, tuple(ReviewIssueType))
        self.assertIn(first_issue.severity, tuple(ReviewSeverity))
        self.assertIsInstance(first_issue.title, str)
        self.assertIsInstance(first_issue.description, str)


if __name__ == "__main__":
    unittest.main()
