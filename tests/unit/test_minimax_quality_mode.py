import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.quality_evaluator import QualityEvaluator
from tencent_doc_review.llm.factory import create_llm_client
from tencent_doc_review.llm.providers.minimax import MiniMaxClient


class MiniMaxQualityModeTests(unittest.IsolatedAsyncioTestCase):
    def test_factory_extends_minimax_timeout(self):
        client = create_llm_client(provider="minimax", api_key="test-key", timeout=30)

        self.assertIsInstance(client, MiniMaxClient)
        self.assertEqual(client.timeout, 120)

    async def test_quality_evaluator_uses_combined_call_for_minimax(self):
        minimax_client = type("MiniMaxClientStub", (), {})()
        minimax_client.model = "MiniMax-M2.7"
        minimax_client.analyze = AsyncMock(
            return_value=Mock(
                content='{"overall_score":81,"overall_level":"good","summary":"整体较完整","priority_improvements":["补充价格来源"],"dimension_scores":[{"dimension":"content_completeness","score":82,"level":"good","strengths":["结构完整"],"weaknesses":["细节可更充分"],"suggestions":["补充案例"]},{"dimension":"logical_clarity","score":80,"level":"good","strengths":["逻辑清晰"],"weaknesses":[],"suggestions":["压缩重复表述"]},{"dimension":"argumentation_quality","score":79,"level":"satisfactory","strengths":["有对比"],"weaknesses":["论据偏少"],"suggestions":["补充数据支持"]},{"dimension":"data_accuracy","score":83,"level":"good","strengths":["表述谨慎"],"weaknesses":[],"suggestions":["补充来源链接"]},{"dimension":"language_expression","score":81,"level":"good","strengths":["表达顺畅"],"weaknesses":[],"suggestions":["再压缩口语化表述"]},{"dimension":"format_compliance","score":78,"level":"satisfactory","strengths":["结构可读"],"weaknesses":[],"suggestions":["保持标题层级一致"]}]}'
            )
        )

        evaluator = QualityEvaluator(llm_client=minimax_client)
        report = await evaluator.evaluate("这是一篇足够长的测试文档，用于验证 MiniMax 总评模式是否生效。" * 20)

        self.assertTrue(evaluator.use_combined_call)
        self.assertEqual(evaluator.timeout_seconds, 120)
        self.assertEqual(minimax_client.analyze.await_count, 1)
        self.assertEqual(report.overall_score, 81.0)


if __name__ == "__main__":
    unittest.main()
