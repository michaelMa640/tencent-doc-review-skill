import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import FactChecker, VerificationStatus


class FactCheckerFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_fact_checker_falls_back_when_llm_extraction_fails(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("llm offline"))
        checker = FactChecker(llm_client=llm_client)

        results = await checker.check("该产品于2025年发布，价格为99元/月。")

        self.assertGreater(len(results), 0)
        self.assertTrue(any("2025年" in item.original_text for item in results))

    async def test_fact_checker_accepts_verification_status_field(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            side_effect=[
                Mock(
                    content='[{"text":"该产品于2025年发布。","claim_type":"date_time","confidence":0.9,"needs_verification":true}]'
                ),
                Mock(
                    content='{"verification_status":"confirmed","confidence":0.9,"evidence":["官网公告"],"sources":[{"title":"官网","url":"https://example.com"}],"suggestion":"无需修改"}'
                ),
            ]
        )
        checker = FactChecker(llm_client=llm_client)

        results = await checker.check("该产品于2025年发布。")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].verification_status, VerificationStatus.CONFIRMED)
        self.assertEqual(results[0].sources[0]["title"], "官网")

    async def test_fact_checker_skips_heading_like_short_lines(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("llm offline"))
        checker = FactChecker(llm_client=llm_client)

        results = await checker.check("对比维度：\n\n价格：\n\n技术：\n\n该产品于2025年发布。")

        self.assertEqual(len(results), 1)
        self.assertIn("2025年", results[0].original_text)

    async def test_fact_checker_skips_obvious_personal_experience_claims(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(side_effect=Exception("llm offline"))
        checker = FactChecker(llm_client=llm_client)

        results = await checker.check(
            "流程顺畅性：从选择形象到生成视频可在3分钟内完成。\n\n视频生成数字人：仅需15秒原始视频即可1:1复刻用户的形象与声音。"
        )

        self.assertEqual(len(results), 1)
        self.assertIn("15秒", results[0].original_text)


if __name__ == "__main__":
    unittest.main()
