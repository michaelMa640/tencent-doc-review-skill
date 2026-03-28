import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.consistency_reviewer import ConsistencyReviewer
from tencent_doc_review.analyzer.language_reviewer import LanguageReviewer
from tencent_doc_review.analyzer.quality_evaluator import QualityDimension, QualityEvaluator
from tencent_doc_review.llm.structured_output import extract_json_payload


class MiniMaxStructuredOutputTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_json_payload_handles_prose_and_code_fences(self):
        payload = extract_json_payload(
            'Here is the result.\n```json\n{"issues":[{"sentence":"原句","title":"语言问题","description":"说明","suggestion":"建议","severity":"medium"}]}\n```'
        )
        self.assertEqual(payload["issues"][0]["title"], "语言问题")

    async def test_language_reviewer_accepts_wrapped_json(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='下面是结果：\n{"issues":[{"sentence":"这句话有问题。","title":"语言表达问题","description":"表达不够自然","suggestion":"建议改写","severity":"medium"}]}'
            )
        )
        reviewer = LanguageReviewer(llm_client)

        issues = await reviewer.review("这句话有问题。")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].title, "语言表达问题")

    async def test_consistency_reviewer_accepts_wrapped_json(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='```json\n{"issues":[{"excerpt_a":"价格为78元","excerpt_b":"价格为98元","description":"前后价格不一致","suggestion":"请统一价格口径","severity":"high"}]}\n```'
            )
        )
        reviewer = ConsistencyReviewer(llm_client)

        issues = await reviewer.review("价格为78元。\n\n价格为98元。")

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].title, "前后矛盾")
        self.assertEqual(issues[0].source_excerpt, "价格为78元")
        self.assertEqual(issues[1].source_excerpt, "价格为98元")

    async def test_quality_evaluator_accepts_wrapped_json(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='分析结果如下：{"score":82,"level":"good","strengths":["结构清晰"],"weaknesses":["论据偏少"],"suggestions":["补充数据支持"],"analysis":"整体较完整"}'
            )
        )
        evaluator = QualityEvaluator(llm_client=llm_client)

        score = await evaluator.evaluate_dimension("这是一个测试文档，包含足够长度用于评估。", QualityDimension.ARGUMENTATION)

        self.assertEqual(score.score, 82.0)
        self.assertEqual(score.level.value, "good")
        self.assertEqual(score.suggestions[0], "补充数据支持")


if __name__ == "__main__":
    unittest.main()
