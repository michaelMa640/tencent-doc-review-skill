"""
事实核查器单元测试

测试 FactChecker 类的所有主要功能。
"""

import pytest
import asyncio
from typing import List
from unittest.mock import AsyncMock, Mock

from tencent_doc_review.analyzer.fact_checker import (
    FactChecker,
    FactCheckResult,
    Claim,
    ClaimType,
    VerificationStatus,
    SearchClient,
    check_facts,
    extract_claims_only
)
from tencent_doc_review.analyzer.fact_checker import MockDeepSeekClient


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    client = Mock()
    
    # 配置 analyze 方法的返回值
    async def mock_analyze(prompt, **kwargs):
        # 根据 prompt 内容返回不同的响应
        if "claim" in prompt.lower() or "声明" in prompt:
            return Mock(content='''[
  {
    "text": "2023年中国GDP增长5.2%",
    "claim_type": "data",
    "confidence": 0.95,
    "needs_verification": true
  },
  {
    "text": "人工智能市场规模达1500亿美元",
    "claim_type": "data",
    "confidence": 0.8,
    "needs_verification": true
  }
]''')
        elif "verify" in prompt.lower() or "验证" in prompt:
            return Mock(content='''{
  "verification_status": "confirmed",
  "confidence": 0.95,
  "evidence": ["国家统计局官方数据"],
  "suggestion": "数据准确"
}''')
        else:
            return Mock(content='{"status": "ok"}')
    
    client.analyze = mock_analyze
    return client


@pytest.fixture
def mock_search_client():
    """Mock 搜索客户端"""
    client = Mock(spec=SearchClient)
    client.search = AsyncMock(return_value=[
        {
            "title": "2023年中国经济数据",
            "snippet": "2023年中国GDP增长5.2%",
            "source": "国家统计局",
            "reliability": 0.95
        }
    ])
    return client


@pytest.fixture
def fact_checker(mock_llm_client, mock_search_client):
    """创建 FactChecker 实例"""
    return FactChecker(
        deepseek_client=mock_llm_client,
        search_client=mock_search_client,
        config={'batch_size': 2}
    )


@pytest.fixture
def sample_text():
    """示例文本"""
    return """
根据国家统计局数据，2023年中国GDP增长5.2%，达到了126万亿元。
人工智能市场规模达到1500亿美元，预计到2025年将增长至2000亿美元。
"""


# ==================== 测试类 ====================

class TestClaimExtraction:
    """测试声明提取功能"""
    
    @pytest.mark.asyncio
    async def test_extract_claims_success(self, fact_checker, sample_text):
        """测试成功提取声明"""
        claims = await fact_checker.extract_claims(sample_text)
        
        assert len(claims) > 0
        assert all(isinstance(c, Claim) for c in claims)
        assert claims[0].text is not None
        assert claims[0].claim_type in [ct for ct in ClaimType]
    
    @pytest.mark.asyncio
    async def test_extract_claims_empty_text(self, fact_checker):
        """测试空文本"""
        claims = await fact_checker.extract_claims("")
        assert len(claims) == 0
    
    @pytest.mark.asyncio
    async def test_extract_claims_no_claims(self, fact_checker):
        """测试无声明的文本"""
        text = "这是一段没有具体事实声明的文本。"
        claims = await fact_checker.extract_claims(text)
        # 可能有也可能没有，取决于LLM的判断
        assert isinstance(claims, list)


class TestClaimVerification:
    """测试声明验证功能"""
    
    @pytest.mark.asyncio
    async def test_verify_claim_success(self, fact_checker):
        """测试成功验证声明"""
        claim = Claim(
            text="2023年中国GDP增长5.2%",
            claim_type=ClaimType.DATA,
            confidence=0.95,
            needs_verification=True
        )
        
        result = await fact_checker.verify_claim(claim)
        
        assert isinstance(result, FactCheckResult)
        assert result.original_text == claim.text
        assert result.verification_status in [vs for vs in VerificationStatus]
        assert 0 <= result.confidence <= 1
    
    @pytest.mark.asyncio
    async def test_verify_claim_no_verification_needed(self, fact_checker):
        """测试不需要验证的声明"""
        claim = Claim(
            text="这是一个观点",
            claim_type=ClaimType.OPINION,
            confidence=0.8,
            needs_verification=False
        )
        
        result = await fact_checker.verify_claim(claim)
        
        assert isinstance(result, FactCheckResult)
        assert result.verification_status == VerificationStatus.UNVERIFIED


class TestFullCheck:
    """测试完整核查流程"""
    
    @pytest.mark.asyncio
    async def test_check_success(self, fact_checker, sample_text):
        """测试完整核查流程"""
        results = await fact_checker.check(sample_text)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, FactCheckResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_check_empty_text(self, fact_checker):
        """测试空文本"""
        results = await fact_checker.check("")
        assert results == []
    
    @pytest.mark.asyncio
    async def test_check_with_context(self, fact_checker, sample_text):
        """测试带上下文的核查"""
        context = {
            'document_type': 'report',
            'topic': 'economy'
        }
        results = await fact_checker.check(sample_text, context)
        
        assert isinstance(results, list)


class TestBatchCheck:
    """测试批量核查功能"""
    
    @pytest.mark.asyncio
    async def test_batch_check_success(self, fact_checker):
        """测试批量核查"""
        texts = [
            "文本1内容",
            "文本2内容",
            "文本3内容"
        ]
        
        results = await fact_checker.batch_check(texts)
        
        assert isinstance(results, list)
        assert len(results) == len(texts)
        assert all(isinstance(r, list) for r in results)
    
    @pytest.mark.asyncio
    async def test_batch_check_empty(self, fact_checker):
        """测试空列表"""
        results = await fact_checker.batch_check([])
        assert results == []
    
    @pytest.mark.asyncio
    async def test_batch_check_with_progress(self, fact_checker):
        """测试带进度回调的批量核查"""
        texts = ["文本1", "文本2"]
        progress_updates = []
        
        def progress_callback(current, total, message):
            progress_updates.append((current, total, message))
        
        results = await fact_checker.batch_check(
            texts,
            progress_callback=progress_callback
        )
        
        assert len(results) == len(texts)
        assert len(progress_updates) > 0


class TestUtilityFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_check_facts(self, mock_llm_client):
        """测试 check_facts 便捷函数"""
        text = "2023年中国GDP增长5.2%"
        
        results = await check_facts(text, mock_llm_client)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, FactCheckResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_extract_claims_only(self, mock_llm_client):
        """测试 extract_claims_only 便捷函数"""
        text = "2023年中国GDP增长5.2%，人工智能市场规模达1500亿美元。"
        
        claims = await extract_claims_only(text, mock_llm_client)
        
        assert isinstance(claims, list)
        assert len(claims) > 0
        assert all(isinstance(c, Claim) for c in claims)


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_document(self, fact_checker):
        """测试大文档处理"""
        # 生成大文本 (约10万字)
        large_text = "这是一段测试文本。" * 5000
        
        import time
        start = time.time()
        
        results = await fact_checker.check(large_text)
        
        elapsed = time.time() - start
        
        assert isinstance(results, list)
        assert elapsed < 60  # 应该在60秒内完成
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, fact_checker):
        """测试并发请求处理"""
        texts = [f"测试文本{i}" for i in range(10)]
        
        import time
        start = time.time()
        
        # 使用 gather 并发执行
        tasks = [fact_checker.check(text) for text in texts]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        
        assert len(results) == 10
        assert elapsed < 30  # 并发应该在30秒内完成


# ==================== 错误处理测试 ====================

class TestErrorHandling:
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_llm_error(self):
        """测试 LLM 错误处理"""
        # 创建一个会抛出异常的 mock
        mock_client = Mock()
        mock_client.analyze = AsyncMock(side_effect=Exception("LLM API error"))
        
        fact_checker = FactChecker(mock_client)
        
        # 应该抛出异常
        with pytest.raises(Exception):
            await fact_checker.extract_claims("测试文本")
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, mock_llm_client):
        """测试无效 JSON 响应处理"""
        # 配置 mock 返回无效 JSON
        mock_llm_client.analyze = AsyncMock(return_value=Mock(content="invalid json"))
        
        fact_checker = FactChecker(mock_llm_client)
        
        # 应该能处理错误并返回空列表
        claims = await fact_checker.extract_claims("测试文本")
        assert isinstance(claims, list)
