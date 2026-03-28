import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tencent_doc_review.analyzer.fact_checker import (
    Claim,
    ClaimType,
    FactCheckResult,
    FactChecker,
    SearchClient,
    VerificationStatus,
    check_facts,
    extract_claims_only,
)


@pytest.fixture
def mock_llm_client():
    client = Mock()

    async def mock_analyze(prompt, **kwargs):
        prompt_lower = prompt.lower()
        if "extracting factual claims" in prompt_lower:
            return Mock(
                content=(
                    '[{"text":"该产品于2025年发布，定价为99元。",'
                    '"claim_type":"data","confidence":0.9,"needs_verification":true}]'
                )
            )
        if "verifying one factual statement" in prompt_lower:
            return Mock(
                content=(
                    '{"verification_status":"confirmed","confidence":0.92,'
                    '"evidence":["官网页面列出正式售价。"],'
                    '"sources":[{"title":"官网","url":"https://example.com"}],'
                    '"suggestion":"可保留该表述。"}'
                )
            )
        return Mock(content="[]")

    client.analyze = mock_analyze
    return client


@pytest.fixture
def mock_search_client():
    client = Mock(spec=SearchClient)
    client.enabled = True
    client.provider = "tavily"
    client.search = AsyncMock(
        return_value=[
            {
                "title": "官网",
                "url": "https://example.com",
                "snippet": "官网页面列出正式售价。",
                "source": "example.com",
            }
        ]
    )
    client.verify_fact = AsyncMock(
        return_value={
            "status": "unverified",
            "confidence": 0.35,
            "evidence": ["需要结合外部来源进一步复核。"],
            "sources": [{"title": "官网", "url": "https://example.com"}],
            "suggestion": "该内容需要复查。",
        }
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def fact_checker(mock_llm_client, mock_search_client):
    return FactChecker(
        llm_client=mock_llm_client,
        search_client=mock_search_client,
        config={"batch_size": 2},
    )


class TestClaimExtraction:
    @pytest.mark.asyncio
    async def test_extract_claims_success(self, fact_checker):
        claims = await fact_checker.extract_claims("该产品于2025年发布，定价为99元。")

        assert len(claims) == 1
        assert claims[0].text == "该产品于2025年发布，定价为99元。"
        assert claims[0].claim_type == ClaimType.DATA

    @pytest.mark.asyncio
    async def test_extract_claims_falls_back_to_heuristics_on_invalid_json(self, mock_llm_client):
        mock_llm_client.analyze = AsyncMock(return_value=Mock(content="invalid json"))
        checker = FactChecker(llm_client=mock_llm_client)

        claims = await checker.extract_claims("该产品于2025年发布，定价为99元。")

        assert isinstance(claims, list)
        assert len(claims) >= 1


class TestClaimVerification:
    @pytest.mark.asyncio
    async def test_verify_claim_success(self, fact_checker):
        claim = Claim(
            text="该产品于2025年发布，定价为99元。",
            claim_type=ClaimType.DATA,
            confidence=0.9,
            needs_verification=True,
        )

        result = await fact_checker.verify_claim(claim)

        assert isinstance(result, FactCheckResult)
        assert result.verification_status == VerificationStatus.CONFIRMED
        assert result.sources[0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_verify_claim_marks_subjective_sentence_without_fact_check(self, fact_checker):
        claim = Claim(
            text="我觉得这个产品的体验更顺手。",
            claim_type=ClaimType.OTHER,
            confidence=0.6,
            needs_verification=False,
        )

        result = await fact_checker.verify_claim(claim)

        assert result.verification_status == VerificationStatus.UNVERIFIED
        assert "主观体验" in result.suggestion

    @pytest.mark.asyncio
    async def test_verify_claim_allows_product_description_without_public_conflict(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='{"status":"unverified","confidence":0.4,"evidence":[],"sources":[],"suggestion":""}'
            )
        )
        search_client = Mock(spec=SearchClient)
        search_client.enabled = False
        search_client.provider = "disabled"
        search_client.verify_fact = AsyncMock(return_value={})
        search_client.close = AsyncMock()

        checker = FactChecker(llm_client=llm_client, search_client=search_client)
        claim = Claim(
            text="该产品支持多语言模板和数字人播报。",
            claim_type=ClaimType.OTHER,
            confidence=0.7,
            needs_verification=True,
        )

        result = await checker.verify_claim(claim)

        assert result.verification_status == VerificationStatus.CONFIRMED
        assert result.suggestion == ""

    @pytest.mark.asyncio
    async def test_verify_claim_marks_implausible_number_for_manual_review(self):
        llm_client = Mock()
        llm_client.analyze = AsyncMock(
            return_value=Mock(
                content='{"status":"unverified","confidence":0.4,"evidence":[],"sources":[],"suggestion":""}'
            )
        )
        search_client = Mock(spec=SearchClient)
        search_client.enabled = False
        search_client.provider = "disabled"
        search_client.verify_fact = AsyncMock(return_value={})
        search_client.close = AsyncMock()

        checker = FactChecker(llm_client=llm_client, search_client=search_client)
        claim = Claim(
            text="该产品市场占有率达到150%。",
            claim_type=ClaimType.DATA,
            confidence=0.8,
            needs_verification=True,
        )

        result = await checker.verify_claim(claim)

        assert result.verification_status == VerificationStatus.UNVERIFIED
        assert "人工二次核查" in result.suggestion


class TestFullCheck:
    @pytest.mark.asyncio
    async def test_check_runs_end_to_end(self, fact_checker):
        results = await fact_checker.check("该产品于2025年发布，定价为99元。")

        assert len(results) == 1
        assert all(isinstance(item, FactCheckResult) for item in results)

    @pytest.mark.asyncio
    async def test_check_empty_text_returns_empty_list(self, fact_checker):
        assert await fact_checker.check("") == []

    @pytest.mark.asyncio
    async def test_batch_check_reports_progress(self, fact_checker):
        progress_updates = []

        def progress_callback(current, total, message):
            progress_updates.append((current, total, message))

        results = await fact_checker.batch_check(
            ["该产品于2025年发布，定价为99元。", "该公司2024年营收增长20%。"],
            progress_callback=progress_callback,
        )

        assert len(results) == 2
        assert len(progress_updates) == 2


class TestFallbackBehavior:
    @pytest.mark.asyncio
    async def test_llm_error_falls_back_to_heuristics(self):
        mock_client = Mock()
        mock_client.analyze = AsyncMock(side_effect=Exception("LLM API error"))
        checker = FactChecker(llm_client=mock_client)

        claims = await checker.extract_claims("该产品于2025年发布，定价为99元。")

        assert isinstance(claims, list)
        assert len(claims) >= 1

    @pytest.mark.asyncio
    async def test_check_skips_heading_like_short_lines(self):
        mock_client = Mock()
        mock_client.analyze = AsyncMock(side_effect=Exception("LLM API error"))
        checker = FactChecker(llm_client=mock_client)

        results = await checker.check("对比维度：\n\n价格：\n\n技术：\n\n该产品于2025年发布。")

        assert len(results) == 1
        assert "2025年" in results[0].original_text

    @pytest.mark.asyncio
    async def test_check_skips_subjective_comparison_claims(self):
        mock_client = Mock()
        mock_client.analyze = AsyncMock(side_effect=Exception("LLM API error"))
        checker = FactChecker(llm_client=mock_client)

        results = await checker.check(
            "功能：大体上这三个平台的功能都大差不差，蝉镜在生成速度和低门槛的形象定制上表现比较突出，闪剪有直播快剪的特色功能。"
        )

        assert results == []


class TestUtilityFunctions:
    @pytest.mark.asyncio
    async def test_check_facts_helper(self, mock_llm_client):
        results = await check_facts("该产品于2025年发布，定价为99元。", mock_llm_client)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_extract_claims_only_helper(self, mock_llm_client):
        claims = await extract_claims_only("该产品于2025年发布，定价为99元。", mock_llm_client)

        assert len(claims) == 1
