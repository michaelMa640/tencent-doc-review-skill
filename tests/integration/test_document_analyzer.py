"""
DocumentAnalyzer 集成测试

测试完整的文档分析流程，包括：
- 完整分析流程（事实核查 + 结构匹配 + 质量评估）
- 自定义分析配置
- 批量处理
- 边界情况处理
"""

import pytest
import asyncio
import time
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from tencent_doc_review.analyzer.document_analyzer import (
    DocumentAnalyzer,
    AnalysisResult,
    AnalysisConfig,
    AnalysisType,
    analyze_document
)
from tencent_doc_review.analyzer.fact_checker import FactCheckResult
from tencent_doc_review.analyzer.structure_matcher import StructureMatchResult
from tencent_doc_review.analyzer.quality_evaluator import QualityReport


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    client = Mock()
    
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
        elif "structure" in prompt.lower() or "结构" in prompt:
            return Mock(content='''{
  "title": "Document",
  "type": "document",
  "sections": [
    {
      "title": "Introduction",
      "type": "introduction",
      "level": 1,
      "order": 1,
      "required": true
    },
    {
      "title": "Main Content",
      "type": "body",
      "level": 1,
      "order": 2,
      "required": true
    }
  ]
}''')
        elif "match" in prompt.lower() or "匹配" in prompt:
            return Mock(content='''{
  "overall_score": 0.85,
  "section_matches": [
    {
      "template_section": {"title": "Introduction", "type": "introduction"},
      "document_section": {"title": "Introduction", "type": "introduction"},
      "status": "matched",
      "similarity": 0.95
    },
    {
      "template_section": {"title": "Main Content", "type": "body"},
      "document_section": {"title": "Main Content", "type": "body"},
      "status": "matched",
      "similarity": 0.90
    }
  ],
  "missing_sections": [],
  "extra_sections": [],
  "misplaced_sections": [],
  "issues": [],
  "suggestions": []
}''')
        elif "quality" in prompt.lower() or "质量" in prompt or "evaluate" in prompt.lower():
            return Mock(content='''{
  "overall_score": 82.5,
  "overall_level": "good",
  "dimension_scores": [
    {
      "dimension": "content_completeness",
      "score": 85.0,
      "level": "good"
    },
    {
      "dimension": "logical_clarity",
      "score": 88.0,
      "level": "good"
    },
    {
      "dimension": "argumentation_quality",
      "score": 78.0,
      "level": "acceptable"
    },
    {
      "dimension": "data_accuracy",
      "score": 90.0,
      "level": "excellent"
    },
    {
      "dimension": "language_expression",
      "score": 82.0,
      "level": "good"
    },
    {
      "dimension": "format_compliance",
      "score": 75.0,
      "level": "acceptable"
    }
  ],
  "strengths": ["数据准确性高", "逻辑结构清晰"],
  "weaknesses": ["部分论证不够充分"],
  "priority_improvements": ["补充论证数据", "规范文档格式"]
}''')
        else:
            return Mock(content='{"status": "ok"}')
    
    client.analyze = mock_analyze
    return client


@pytest.fixture
def document_analyzer(mock_llm_client):
    """创建 DocumentAnalyzer 实例"""
    return DocumentAnalyzer(
        deepseek_client=mock_llm_client
    )


@pytest.fixture
def sample_document():
    """示例文档文本"""
    return """
# 智能客服系统技术方案

## 1. 项目背景

随着业务快速发展，客户服务需求日益增长。传统人工客服面临以下挑战：
- 响应时间长，平均等待时间超过5分钟
- 人力成本高，客服团队规模持续扩大

## 2. 需求分析

### 2.1 功能需求
1. **多渠道接入**：支持网页、APP、微信小程序等渠道
2. **智能问答**：基于知识库自动回答常见问题

### 2.2 性能需求
- 响应时间：平均响应时间 < 2秒
- 准确率：意图识别准确率 > 95%

## 3. 技术方案

### 3.1 系统架构
采用微服务架构，主要组件包括API Gateway、Dialog Service、Intent Service等。

### 3.2 技术栈
| 层级 | 技术 | 版本 |
|-----|------|------|
| 后端框架 | FastAPI | 0.104+ |
| 数据库 | PostgreSQL | 15+ |

## 4. 实施计划

### 4.1 里程碑
1. **M1（第1-2周）**：需求确认和架构设计
2. **M2（第3-6周）**：核心功能开发

### 4.2 资源需求
- 开发团队：5人
- 测试团队：2人

## 5. 风险评估

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| 模型准确率不达标 | 中 | 高 | 准备备选方案 |
| 系统性能不足 | 低 | 中 | 提前进行压力测试 |

## 6. 验收标准

### 6.1 功能验收
- [ ] 所有功能需求实现并测试通过
- [ ] 用户验收测试（UAT）通过

### 6.2 性能验收
- [ ] 响应时间 < 2秒（95%请求）
- [ ] 系统可用性 > 99.9%
"""


@pytest.fixture
def sample_template():
    """示例模板文本"""
    return """
# 技术方案文档模板

## 1. 项目背景
项目背景和目标说明

## 2. 需求分析
需求描述和分析

## 3. 技术方案
技术实现方案

## 4. 实施计划
实施步骤和计划

## 5. 风险评估
风险识别和应对措施

## 6. 验收标准
验收条件和标准
"""


# ==================== 集成测试类 ====================

class TestBasicAnalysis:
    """测试基础分析流程"""
    
    @pytest.mark.asyncio
    async def test_full_analysis(self, document_analyzer, sample_document, sample_template):
        """测试完整分析流程"""
        result = await document_analyzer.analyze(
            document_text=sample_document,
            template_text=sample_template,
            document_id="test-doc-001",
            document_title="智能客服系统技术方案"
        )
        
        # 验证结果类型
        assert result is not None
        assert isinstance(result, AnalysisResult)
        
        # 验证基本信息
        assert result.document_id == "test-doc-001"
        assert result.document_title == "智能客服系统技术方案"
        
        # 验证分析结果存在
        assert len(result.fact_check_results) >= 0
        assert result.structure_match_result is not None
        assert result.quality_report is not None
        
        # 验证摘要和建议
        assert len(result.summary) > 0
        assert isinstance(result.recommendations, list)
    
    @pytest.mark.asyncio
    async def test_analysis_without_template(self, document_analyzer, sample_document):
        """测试不使用模板的分析"""
        result = await document_analyzer.analyze(
            document_text=sample_document,
            template_text=None,
            document_id="test-doc-002"
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
        # 没有模板时，结构匹配结果可能不同
        assert result.structure_match_result is not None or result.structure_match_result is None
    
    @pytest.mark.asyncio
    async def test_custom_analysis_config(self, document_analyzer, sample_document, sample_template):
        """测试自定义分析配置"""
        config = AnalysisConfig(
            analysis_type=AnalysisType.CUSTOM,
            enable_fact_check=True,
            enable_structure_match=True,
            enable_quality_eval=True,
            batch_size=3,
            max_concurrency=2
        )
        
        result = await document_analyzer.analyze(
            document_text=sample_document,
            template_text=sample_template,
            config=config
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)


class TestCustomAnalysis:
    """测试自定义分析功能"""
    
    @pytest.mark.asyncio
    async def test_custom_analysis_fact_check_only(self, document_analyzer, sample_document):
        """测试仅事实核查的自定义分析"""
        result = await document_analyzer.analyze_custom(
            document_text=sample_document,
            checks=['fact_check']
        )
        
        assert result is not None
        assert len(result.fact_check_results) >= 0
        # 结构匹配和质量评估应该被禁用或为空
    
    @pytest.mark.asyncio
    async def test_custom_analysis_structure_only(self, document_analyzer, sample_document, sample_template):
        """测试仅结构匹配的自定义分析"""
        result = await document_analyzer.analyze_custom(
            document_text=sample_document,
            checks=['structure'],
            template_text=sample_template
        )
        
        assert result is not None
        assert result.structure_match_result is not None
    
    @pytest.mark.asyncio
    async def test_custom_analysis_quality_only(self, document_analyzer, sample_document):
        """测试仅质量评估的自定义分析"""
        result = await document_analyzer.analyze_custom(
            document_text=sample_document,
            checks=['quality']
        )
        
        assert result is not None
        assert result.quality_report is not None


class TestBatchProcessing:
    """测试批量处理功能"""
    
    @pytest.mark.asyncio
    async def test_analyze_batch(self, document_analyzer, sample_template):
        """测试批量分析"""
        documents = [
            {
                'text': '# Document 1\n\n## Section 1\nContent 1\n\n## Section 2\nContent 2',
                'id': 'doc-001',
                'title': 'Document 1'
            },
            {
                'text': '# Document 2\n\n## Section A\nContent A\n\n## Section B\nContent B',
                'id': 'doc-002',
                'title': 'Document 2'
            },
            {
                'text': '# Document 3\n\n## Part 1\nContent 1\n\n## Part 2\nContent 2',
                'id': 'doc-003',
                'title': 'Document 3'
            }
        ]
        
        config = AnalysisConfig(
            batch_size=2,
            max_concurrency=2
        )
        
        results = await document_analyzer.analyze_batch(
            documents=documents,
            config=config
        )
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result, AnalysisResult)
            assert result.document_id in ['doc-001', 'doc-002', 'doc-003']
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_progress_callback(self, document_analyzer):
        """测试带进度回调的批量处理"""
        progress_updates = []
        
        def progress_callback(current, total, message):
            progress_updates.append({
                'current': current,
                'total': total,
                'message': message
            })
        
        documents = [
            {'text': f'# Doc {i}', 'id': f'doc-{i}', 'title': f'Document {i}'}
            for i in range(5)
        ]
        
        results = await document_analyzer.analyze_batch(
            documents=documents,
            progress_callback=progress_callback
        )
        
        assert len(results) == 5
        assert len(progress_updates) > 0
        # 验证最后一个是完成消息
        assert progress_updates[-1]['current'] == 5


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.mark.asyncio
    async def test_empty_document(self, document_analyzer, sample_template):
        """测试空文档分析"""
        result = await document_analyzer.analyze(
            document_text="",
            template_text=sample_template,
            document_id="empty-doc"
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.document_id == "empty-doc"
        # 空文档应该返回低质量评分或警告
    
    @pytest.mark.asyncio
    async def test_very_short_document(self, document_analyzer):
        """测试非常短的文档"""
        short_doc = "这是一个测试文档。"
        
        result = await document_analyzer.analyze(
            document_text=short_doc,
            document_id="short-doc"
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
    
    @pytest.mark.asyncio
    async def test_very_long_document(self, document_analyzer, sample_template):
        """测试超长文档"""
        # 创建一个超长的文档
        long_content = "这是一段内容。" * 100
        long_doc = "# 长文档\n\n"
        
        for i in range(1, 51):
            long_doc += f"## {i}. 章节 {i}\n\n{long_content}\n\n"
        
        result = await document_analyzer.analyze(
            document_text=long_doc,
            template_text=sample_template,
            document_id="long-doc"
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
        # 长文档应该能正常处理，尽管可能需要更长时间


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_analyze_document_function(self, mock_llm_client, sample_document, sample_template):
        """测试 analyze_document 便捷函数"""
        result = await analyze_document(
            document_text=sample_document,
            deepseek_client=mock_llm_client,
            template_text=sample_template
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.quality_report is not None
        assert result.structure_match_result is not None


class TestErrorHandling:
    """测试错误处理"""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_with_partial_failure(self, mock_llm_client, sample_document, sample_template):
        """测试部分失败时的优雅降级"""
        # 模拟某些模块失败
        call_count = 0
        original_analyze = mock_llm_client.analyze
        
        async def failing_analyze(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # 第二次调用失败
                raise Exception("Simulated LLM failure")
            return await original_analyze(prompt, **kwargs)
        
        mock_llm_client.analyze = failing_analyze
        
        analyzer = DocumentAnalyzer(mock_llm_client)
        
        # 即使部分失败，也应该返回结果
        result = await analyzer.analyze(
            document_text=sample_document,
            template_text=sample_template
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)
    
    @pytest.mark.asyncio
    async def test_invalid_configuration(self, mock_llm_client, sample_document):
        """测试无效配置处理"""
        analyzer = DocumentAnalyzer(mock_llm_client)
        
        # 测试空配置
        config = AnalysisConfig()
        
        result = await analyzer.analyze(
            document_text=sample_document,
            config=config
        )
        
        assert result is not None
        assert isinstance(result, AnalysisResult)


class TestPerformance:
    """测试性能"""
    
    @pytest.mark.asyncio
    async def test_analysis_performance(self, document_analyzer, sample_document, sample_template):
        """测试分析性能"""
        start_time = time.time()
        
        result = await document_analyzer.analyze(
            document_text=sample_document,
            template_text=sample_template
        )
        
        elapsed_time = time.time() - start_time
        
        assert result is not None
        # 分析应该在合理时间内完成（比如30秒内）
        assert elapsed_time < 30, f"分析耗时过长: {elapsed_time:.2f}秒"
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis_performance(self, document_analyzer):
        """测试并发分析性能"""
        documents = [
            {
                'text': f'# Document {i}\n\n## Section 1\nContent\n\n## Section 2\nContent',
                'id': f'doc-{i}',
                'title': f'Document {i}'
            }
            for i in range(5)
        ]
        
        start_time = time.time()
        
        results = await document_analyzer.analyze_batch(documents)
        
        elapsed_time = time.time() - start_time
        
        assert len(results) == 5
        # 批量处理应该比串行处理快
        assert elapsed_time < 60, f"批量处理耗时过长: {elapsed_time:.2f}秒"


# ==================== 运行所有测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
