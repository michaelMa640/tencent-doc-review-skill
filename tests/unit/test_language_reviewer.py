import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.language_reviewer import LanguageReviewer
from tencent_doc_review.domain import ReviewIssueType


class LanguageReviewerTests(unittest.IsolatedAsyncioTestCase):
    async def test_language_reviewer_fallback_detects_colloquial_sentence(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("offline"))
        reviewer = LanguageReviewer(llm_client)

        issues = await reviewer.review("这个功能大差不差，整体效果还行。")

        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].issue_type, ReviewIssueType.LANGUAGE)
        self.assertIn("口语化", issues[0].description)

    async def test_language_reviewer_parses_llm_json(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='{"issues":[{"sentence":"这句话有问题。","title":"语言表达问题","description":"表达不够自然","suggestion":"建议改写","severity":"medium"}]}'
            )
        )
        reviewer = LanguageReviewer(llm_client)

        issues = await reviewer.review("这句话有问题。")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].source_excerpt, "这句话有问题。")
        self.assertEqual(issues[0].title, "语言表达问题")
        self.assertEqual(issues[0].suggestion, "建议改写")

    async def test_language_reviewer_detects_english_spelling_issue(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("offline"))
        reviewer = LanguageReviewer(llm_client)

        issues = await reviewer.review("This enviroment is easy to use.")

        self.assertEqual(len(issues), 1)
        self.assertIn("拼写", issues[0].title)
        self.assertIn("enviroment", issues[0].description)

    async def test_language_reviewer_retries_before_fallback(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            side_effect=[Exception("timeout"), Mock(content='{"issues": []}')]
        )
        reviewer = LanguageReviewer(llm_client, config={"max_retries": 2, "retry_delay_seconds": 0})

        issues = await reviewer.review("这个功能大差不差，整体效果还行。")

        self.assertGreaterEqual(llm_client.analyze.await_count, 2)
        self.assertGreaterEqual(len(issues), 1)

    async def test_language_reviewer_skips_heading_like_english_line(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("offline"))
        reviewer = LanguageReviewer(llm_client)

        issues = await reviewer.review("## I. Product Overview")

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
