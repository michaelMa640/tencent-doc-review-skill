import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.document_analyzer import DocumentAnalyzer
from tencent_doc_review.analyzer.fact_checker import FactChecker
from tencent_doc_review.analyzer.quality_evaluator import QualityEvaluator
from tencent_doc_review.analyzer.structure_matcher import StructureMatcher
from tencent_doc_review.llm import SUPPORTED_PROVIDERS
from tencent_doc_review.llm.factory import create_llm_client
from tencent_doc_review.llm.providers.minimax import MiniMaxClient
from tencent_doc_review.llm.providers.mock import MockLLMClient


class Phase3LLMInterfaceTests(unittest.TestCase):
    def test_supported_providers_are_explicit(self):
        self.assertEqual(SUPPORTED_PROVIDERS, ("deepseek", "minimax", "mock", "openai"))

    def test_minimax_provider_can_be_created(self):
        client = create_llm_client(provider="minimax", api_key="test-key")
        self.assertIsInstance(client, MiniMaxClient)

    def test_document_analyzer_accepts_llm_client(self):
        analyzer = DocumentAnalyzer(llm_client=MockLLMClient())
        self.assertIsNotNone(analyzer.llm_client)

    def test_legacy_deepseek_client_argument_is_still_supported(self):
        analyzer = DocumentAnalyzer(deepseek_client=MockLLMClient())
        self.assertIsNotNone(analyzer.llm_client)

    def test_sub_analyzers_accept_llm_client(self):
        llm_client = MockLLMClient()
        self.assertIsNotNone(FactChecker(llm_client=llm_client))
        self.assertIsNotNone(QualityEvaluator(llm_client=llm_client))
        self.assertIsNotNone(StructureMatcher(llm_client=llm_client))


if __name__ == "__main__":
    unittest.main()
