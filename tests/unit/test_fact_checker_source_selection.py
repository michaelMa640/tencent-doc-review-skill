import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import Claim, ClaimType, FactChecker
from tencent_doc_review.llm.providers.mock import MockLLMClient


class FactCheckerSourceSelectionTests(unittest.TestCase):
    def test_irrelevant_numeric_source_snippet_is_filtered_out(self):
        checker = FactChecker(llm_client=MockLLMClient())
        claim = Claim(
            text="全球 Generative AI 市场在 2024 年已达约 168.7 亿美元。",
            claim_type=ClaimType.DATA,
        )
        results = [
            {
                "title": "Patent Review",
                "url": "https://example.com/patent-review",
                "raw_content": "Table 10: Patent Review of Generative AI, by Year, 2021-November 2024. Table 11: Top Patent Owner in Generative AI, by Year, 2014-2023.",
                "snippet": "",
            }
        ]

        refined = checker._refine_search_result_snippets(claim, results)

        self.assertEqual(refined, [])


if __name__ == "__main__":
    unittest.main()
