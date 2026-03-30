import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.structure_matcher import StructureMatcher
from tencent_doc_review.llm.providers.mock import MockLLMClient


class StructureMatcherAliasTests(unittest.IsolatedAsyncioTestCase):
    async def test_conclusion_alias_matches_template_section(self):
        matcher = StructureMatcher(llm_client=MockLLMClient())
        template = "# 产品概述\n\n# 结论与推荐建议"
        document = "一、产品概述\n\n八、总结与建议"

        result = await matcher.match(document, template)

        statuses = {item.template_section.title: item.status.value for item in result.section_matches}
        self.assertEqual(statuses["产品概述"], "matched")
        self.assertEqual(statuses["结论与推荐建议"], "matched")
        self.assertAlmostEqual(result.overall_score, 1.0)


if __name__ == "__main__":
    unittest.main()
