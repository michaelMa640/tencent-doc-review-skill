import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.document_analyzer import DocumentAnalyzer
from tencent_doc_review.analyzer.fact_checker import FactChecker
from tencent_doc_review.analyzer.quality_evaluator import QualityEvaluator
from tencent_doc_review.analyzer.structure_matcher import StructureMatcher
from tencent_doc_review.llm import SUPPORTED_PROVIDERS
from tencent_doc_review.llm.factory import create_llm_client, resolve_llm_settings
from tencent_doc_review.llm.providers.minimax import MiniMaxClient
from tencent_doc_review.llm.providers.mock import MockLLMClient


class Phase3LLMInterfaceTests(unittest.TestCase):
    def test_supported_providers_are_explicit(self):
        self.assertEqual(SUPPORTED_PROVIDERS, ("deepseek", "minimax", "mock", "openai"))

    def test_minimax_provider_can_be_created(self):
        client = create_llm_client(provider="minimax", api_key="test-key")
        self.assertIsInstance(client, MiniMaxClient)

    def test_provider_specific_runtime_settings_can_coexist(self):
        settings = SimpleNamespace(
            llm_provider="deepseek",
            llm_api_key="",
            llm_base_url="https://api.deepseek.com/v1",
            llm_model="deepseek-chat",
            deepseek_api_key="deepseek-key",
            deepseek_base_url="https://api.deepseek.com/v1",
            deepseek_model="deepseek-chat",
            minimax_api_key="minimax-key",
            minimax_base_url="https://api.minimaxi.com/v1",
            minimax_model="MiniMax-M2.7",
            request_timeout=30,
        )

        deepseek_settings = resolve_llm_settings(settings, provider="deepseek")
        minimax_settings = resolve_llm_settings(settings, provider="minimax")

        self.assertEqual(deepseek_settings["api_key"], "deepseek-key")
        self.assertEqual(minimax_settings["api_key"], "minimax-key")
        self.assertEqual(minimax_settings["base_url"], "https://api.minimaxi.com/v1")
        self.assertEqual(minimax_settings["model"], "MiniMax-M2.7")

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

    def test_mock_provider_exposes_capabilities(self):
        capabilities = MockLLMClient().get_capabilities()

        self.assertEqual(capabilities.provider, "mock")
        self.assertFalse(capabilities.supports_native_web_search)


if __name__ == "__main__":
    unittest.main()
