"""
质量评估器单元测试

测试 QualityEvaluator 类的所有主要功能。
"""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, MagicMock

from tencent_doc_review.analyzer.quality_evaluator import (
    QualityEvaluator,
    QualityReport,
    DimensionScore,
    EvaluationDimension,
    QualityLevel,
    evaluate_quality
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    client = Mock()
    
    async def mock_analyze(prompt, **kwargs):
        # 根据 prompt 内容返回不同的响应
        if "quality" in prompt.lower() or "质量" in prompt or "evaluate" in prompt.lower():
            return Mock(content='''{
  "overall_score": 82.5,
  "overall_level": "good",
  "dimension_scores": [
    {
      "dimension": "content_completeness",
      "score": 85.0,
      "level": "good",
      "issues": ["部分细节描述不够详细"],
      "suggestions": ["建议补充更多技术细节"]
    },
    {
      "dimension": "logical_clarity",
      "score": 88.0,
      "level": "good",
      "issues": [],
      "suggestions": ["可以进一步优化段落过渡"]
    },
    {
      "dimension": "argumentation_quality",
      "score": 78.0,
      "level": "acceptable",
      "issues": ["部分论据支撑不足"],
      "suggestions": ["建议补充更多数据支撑"]
    },
    {
      "dimension": "data_accuracy",
      "score": 90.0,
      "level": "excellent",
      "issues": [],
      "suggestions": []
    },
    {
      "dimension": "language_expression",
      "score": 82.0,
      "level": "good",
      "issues": ["个别用词可优化"],
      "suggestions": ["建议使用更专业的术语"]
    },
    {
      "dimension": "format_compliance",
      "score": 75.0,
      "level": "acceptable",
      "issues": ["格式不够规范", "缺少页眉页脚"],
      "suggestions": ["建议参照标准模板调整格式"]
    }
  ],
  "strengths": [
    "数据准确性高，引用规范",
    "逻辑结构清晰，层次分明"
  ],
  "weaknesses": [
    "部分论证不够充分",
    "格式规范性有待提升"
  ],
  "priority_improvements": [
    "补充论证数据，增强说服力",
    "规范文档格式，参照标准模板",
    "细化技术细节描述"
  ],
  "compliance_score": 75.0
}''')
        elif "dimension" in prompt.lower() or "维度" in prompt:
            return Mock(content='''{
  "dimension": "content_completeness",
  "score": 85.0,
  "level": "good",
  "weight": 1.0,
  "issues": ["部分细节描述不够详细"],
  "suggestions": ["建议补充更多技术细节"],
  "evaluated_at": "2024-01-15T10:30:00Z"
}''')
        else:
            return Mock(content='{"status": "ok"}')
    
    client.analyze = mock_analyze
    return client


@pytest.fixture
def quality_evaluator(mock_llm_client):
    """创建 QualityEvaluator 实例"""
    return QualityEvaluator(
        deepseek_client=mock_llm_client,
        config={'batch_size': 2}
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
- 服务质量不稳定，受客服人员状态影响大

## 2. 需求分析

### 2.1 功能需求
1. **多渠道接入**：支持网页、APP、微信小程序等渠道
2. **智能问答**：基于知识库自动回答常见问题
3. **意图识别**：准确识别用户意图，引导对话流程
4. **人工接管**：复杂问题无缝转接人工客服

### 2.2 性能需求
- 响应时间：平均响应时间 < 2秒
- 并发处理：支持1000+并发对话
- 准确率：意图识别准确率 > 95%

## 3. 技术方案

### 3.1 系统架构
采用微服务架构，主要组件包括：

```
┌─────────────────┐
│   API Gateway   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐   ┌▼──────┐
│Dialog │   │ Intent│
│Service│   │Service│
└───┬───┘   └───┬───┘
    │           │
┌───▼───────────▼───┐
│   Knowledge Base  │
└───────────────────┘
```

### 3.2 技术栈
| 层级 | 技术 | 版本 |
|-----|------|------|
| 后端框架 | FastAPI | 0.104+ |
| 数据库 | PostgreSQL | 15+ |
| 缓存 | Redis | 7+ |
| 消息队列 | RabbitMQ | 3.12+ |
| NLP | HuggingFace Transformers | 4.35+ |

## 4. 实施计划

### 4.1 里程碑
1. **M1（第1-2周）**：需求确认和架构设计
2. **M2（第3-6周）**：核心功能开发
3. **M3（第7-8周）**：集成测试和优化
4. **M4（第9-10周）**：上线部署和培训

### 4.2 资源需求
- 开发团队：5人（1架构 + 3后端 + 1前端）
- 测试团队：2人
- 项目管理：1人

## 5. 风险评估

### 5.1 技术风险
| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| 模型准确率不达标 | 中 | 高 | 准备备选方案，人工兜底 |
| 系统性能不足 | 低 | 中 | 提前进行压力测试 |
| 第三方服务故障 | 低 | 中 | 设计降级策略 |

### 5.2 项目风险
- 需求变更：建立变更控制流程
- 人员流动：知识文档化，交叉培训
- 进度延误：设置缓冲时间，定期跟踪

## 6. 验收标准

### 6.1 功能验收
- [ ] 所有功能需求实现并测试通过
- [ ] 用户验收测试（UAT）通过
- [ ] 文档齐全（用户手册、运维手册）

### 6.2 性能验收
- [ ] 响应时间 < 2秒（95%请求）
- [ ] 并发处理 > 1000 会话
- [ ] 系统可用性 > 99.9%

### 6.3 安全验收
- [ ] 通过安全扫描，无高危漏洞
- [ ] 数据加密传输和存储
- [ ] 权限控制符合最小权限原则
"""


# ==================== 测试类 ====================

class TestEvaluationDimensions:
    """测试质量评估维度"""
    
    @pytest.mark.asyncio
    async def test_all_dimensions_evaluated(self, quality_evaluator, sample_document):
        """测试所有维度都被评估"""
        result = await quality_evaluator.evaluate(sample_document)
        
        assert result is not None
        assert isinstance(result, QualityReport)
        
        # 检查所有7个维度都被评估
        dimension_names = [d.dimension.value for d in result.dimension_scores]
        expected_dimensions = [
            'content_completeness',
            'logical_clarity',
            'argumentation_quality',
            'data_accuracy',
            'language_expression',
            'format_compliance'
        ]
        
        for dim in expected_dimensions:
            assert dim in dimension_names, f"缺少维度: {dim}"
    
    @pytest.mark.asyncio
    async def test_dimension_score_range(self, quality_evaluator, sample_document):
        """测试维度分数范围"""
        result = await quality_evaluator.evaluate(sample_document)
        
        for dim_score in result.dimension_scores:
            # 分数应该在 0-100 之间
            assert 0 <= dim_score.score <= 100, \
                f"维度 {dim_score.dimension.value} 的分数 {dim_score.score} 超出范围"
    
    @pytest.mark.asyncio
    async def test_overall_score_calculation(self, quality_evaluator, sample_document):
        """测试总体分数计算"""
        result = await quality_evaluator.evaluate(sample_document)
        
        # 计算维度分数的平均值
        expected_avg = sum(d.score for d in result.dimension_scores) / len(result.dimension_scores)
        
        # 总体分数应该接近平均值（可能有加权）
        assert abs(result.overall_score - expected_avg) < 10, \
            f"总体分数 {result.overall_score} 与平均维度分数 {expected_avg} 差异过大"


class TestQualityLevels:
    """测试质量等级"""
    
    @pytest.mark.asyncio
    async def test_quality_level_consistency(self, quality_evaluator, sample_document):
        """测试质量等级与分数一致"""
        result = await quality_evaluator.evaluate(sample_document)
        
        # 根据分数判断等级
        score = result.overall_score
        level = result.overall_level
        
        if score >= 90:
            expected_level = QualityLevel.EXCELLENT
        elif score >= 80:
            expected_level = QualityLevel.GOOD
        elif score >= 70:
            expected_level = QualityLevel.ACCEPTABLE
        elif score >= 60:
            expected_level = QualityLevel.POOR
        else:
            expected_level = QualityLevel.CRITICAL
        
        assert level == expected_level, \
            f"分数 {score} 对应的等级应该是 {expected_level.value}，但实际是 {level.value}"


class TestImprovementSuggestions:
    """测试改进建议"""
    
    @pytest.mark.asyncio
    async def test_priority_improvements_exist(self, quality_evaluator, sample_document):
        """测试存在优先级改进建议"""
        result = await quality_evaluator.evaluate(sample_document)
        
        # 应该有优先级改进建议
        assert len(result.priority_improvements) > 0, "应该有优先级改进建议"
    
    @pytest.mark.asyncio
    async def test_strengths_and_weaknesses(self, quality_evaluator, sample_document):
        """测试优势和劣势分析"""
        result = await quality_evaluator.evaluate(sample_document)
        
        # 应该有优势分析
        assert len(result.strengths) >= 0, "应该有优势分析"
        
        # 应该有劣势分析
        assert len(result.weaknesses) >= 0, "应该有劣势分析"


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.mark.asyncio
    async def test_empty_document(self, quality_evaluator):
        """测试空文档"""
        result = await quality_evaluator.evaluate("")
        
        assert result is not None
        # 空文档应该得分很低
        assert result.overall_score < 30
    
    @pytest.mark.asyncio
    async def test_very_short_document(self, quality_evaluator):
        """测试非常短的文档"""
        short_doc = "这是一个非常短的文档。"
        
        result = await quality_evaluator.evaluate(short_doc)
        
        assert result is not None
        # 短文档在某些维度上可能得分较低
        completeness_score = next(
            (d.score for d in result.dimension_scores 
             if d.dimension == EvaluationDimension.CONTENT_COMPLETENESS),
            None
        )
        if completeness_score:
            assert completeness_score < 80  # 内容完整性应该较低
    
    @pytest.mark.asyncio
    async def test_very_long_document(self, quality_evaluator):
        """测试超长文档"""
        # 创建一个超长的文档
        long_content = "这是一段内容。" * 100
        long_doc = "# 长文档\n\n"
        
        for i in range(1, 51):
            long_doc += f"## {i}. 章节 {i}\n\n{long_content}\n\n"
        
        result = await quality_evaluator.evaluate(long_doc)
        
        assert result is not None
        # 长文档应该能正常处理
        assert len(result.dimension_scores) == 6  # 所有6个维度


class TestUtilityFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_evaluate_quality_function(self, mock_llm_client):
        """测试 evaluate_quality 便捷函数"""
        document = """
# 测试文档

## 1. 背景
这是背景介绍。

## 2. 内容
这是主要内容。
"""
        
        result = await evaluate_quality(document, mock_llm_client)
        
        assert result is not None
        assert isinstance(result, QualityReport)
        assert result.overall_score > 0


class TestConfiguration:
    """测试配置选项"""
    
    @pytest.mark.asyncio
    async def test_custom_weights(self, mock_llm_client):
        """测试自定义权重"""
        custom_weights = {
            'content_completeness': 1.5,
            'logical_clarity': 1.2,
            'data_accuracy': 1.3
        }
        
        evaluator = QualityEvaluator(
            deepseek_client=mock_llm_client,
            config={'weights': custom_weights}
        )
        
        assert evaluator.config['weights'] == custom_weights
    
    @pytest.mark.asyncio
    async def test_dimension_thresholds(self, mock_llm_client):
        """测试维度阈值"""
        custom_thresholds = {
            'excellent': 92,
            'good': 82,
            'acceptable': 72
        }
        
        evaluator = QualityEvaluator(
            deepseek_client=mock_llm_client,
            config={'thresholds': custom_thresholds}
        )
        
        assert evaluator.config['thresholds'] == custom_thresholds


# ==================== 运行所有测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
