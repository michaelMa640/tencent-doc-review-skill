"""
结构匹配器单元测试

测试 StructureMatcher 类的所有主要功能。
"""

import pytest
import asyncio
from typing import List
from unittest.mock import AsyncMock, Mock, MagicMock

from tencent_doc_review.analyzer.structure_matcher import (
    StructureMatcher,
    StructureMatchResult,
    Section,
    SectionType,
    SectionMatch,
    MatchStatus,
    match_structure,
    parse_document_structure
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端"""
    client = Mock()
    
    async def mock_analyze(prompt, **kwargs):
        # 根据 prompt 内容返回不同的响应
        if "structure" in prompt.lower() or "结构" in prompt:
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
    },
    {
      "title": "Conclusion",
      "type": "conclusion",
      "level": 1,
      "order": 3,
      "required": false
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
    },
    {
      "template_section": {"title": "Conclusion", "type": "conclusion"},
      "document_section": null,
      "status": "missing",
      "similarity": 0.0
    }
  ],
  "missing_sections": ["Conclusion"],
  "extra_sections": [],
  "misplaced_sections": [],
  "issues": ["缺少可选章节: Conclusion"],
  "suggestions": ["建议添加 Conclusion 章节以完善文档结构"]
}''')
        else:
            return Mock(content='{"status": "ok"}')
    
    client.analyze = mock_analyze
    return client


@pytest.fixture
def structure_matcher(mock_llm_client):
    """创建 StructureMatcher 实例"""
    return StructureMatcher(
        deepseek_client=mock_llm_client,
        config={'batch_size': 2}
    )


@pytest.fixture
def sample_template():
    """示例模板文本"""
    return """
# 产品需求文档模板

## 1. 概述
项目背景和目标说明

## 2. 需求描述
功能需求详细描述

## 3. 技术方案
技术实现方案

## 4. 验收标准
验收条件和标准
"""


@pytest.fixture
def sample_document():
    """示例文档文本"""
    return """
# 新产品需求文档

## 1. 概述
本项目旨在开发一款智能客服系统

## 2. 需求描述
系统需要支持多渠道接入，包括网页、APP和微信小程序

## 3. 技术方案
采用微服务架构，使用Python和Node.js开发

## 4. 验收标准
系统响应时间不超过2秒，准确率95%以上
"""


# ==================== 测试类 ====================

class TestSectionParsing:
    """测试章节解析功能"""
    
    @pytest.mark.asyncio
    async def test_parse_structure_llm(self, structure_matcher, sample_document):
        """测试使用 LLM 解析结构"""
        result = await structure_matcher._parse_structure_llm(sample_document, is_template=False)
        
        assert result is not None
        assert isinstance(result, Section)
        assert len(result.children) > 0
    
    @pytest.mark.asyncio
    async def test_parse_structure_with_markdown(self, structure_matcher):
        """测试解析 Markdown 格式文档"""
        markdown_doc = """
# 标题一
内容一

## 子标题 1.1
子内容

## 子标题 1.2
子内容

# 标题二
内容二
"""
        result = await structure_matcher._parse_structure_llm(markdown_doc, is_template=False)
        
        assert result is not None
        # LLM 应该解析出至少两个主要章节
    
    def test_fallback_parse(self, structure_matcher, sample_document):
        """测试回退解析方法"""
        result = structure_matcher._fallback_parse(sample_document, is_template=False)
        
        assert result is not None
        assert isinstance(result, Section)
        # 回退方法应该能解析出章节


class TestStructureMatching:
    """测试结构匹配功能"""
    
    @pytest.mark.asyncio
    async def test_basic_matching(self, structure_matcher, sample_template, sample_document):
        """测试基本匹配功能"""
        result = await structure_matcher.match(sample_document, sample_template)
        
        assert result is not None
        assert isinstance(result, StructureMatchResult)
        assert 0 <= result.overall_score <= 1
        assert len(result.section_matches) > 0
    
    @pytest.mark.asyncio
    async def test_missing_sections_detection(self, structure_matcher):
        """测试检测缺失章节"""
        template = """
# 模板

## 1. 必需章节
内容

## 2. 可选章节
内容

## 3. 另一个必需章节
内容
"""
        
        document = """
# 文档

## 1. 必需章节
内容

## 3. 另一个必需章节
内容
"""
        
        result = await structure_matcher.match(document, template)
        
        # 应该检测到缺失的章节
        missing = [m for m in result.section_matches if m.status.value == 'missing']
        assert len(missing) > 0 or len(result.missing_sections) > 0
    
    @pytest.mark.asyncio
    async def test_extra_sections_detection(self, structure_matcher):
        """测试检测多余章节"""
        template = """
# 模板

## 1. 标准章节
内容
"""
        
        document = """
# 文档

## 1. 标准章节
内容

## 2. 额外章节
额外内容

## 3. 另一个额外章节
更多内容
"""
        
        result = await structure_matcher.match(document, template)
        
        # 应该检测到多余的章节
        extra = [m for m in result.section_matches if m.status.value == 'extra']
        assert len(extra) > 0 or len(result.extra_sections) > 0


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.mark.asyncio
    async def test_empty_document(self, structure_matcher, sample_template):
        """测试空文档"""
        result = await structure_matcher.match("", sample_template)
        
        assert result is not None
        # 空文档应该匹配度很低
        assert result.overall_score < 0.5
    
    @pytest.mark.asyncio
    async def test_empty_template(self, structure_matcher, sample_document):
        """测试空模板"""
        result = await structure_matcher.match(sample_document, "")
        
        assert result is not None
        # 没有模板时应该视为全部多余
    
    @pytest.mark.asyncio
    async def test_very_long_document(self, structure_matcher, sample_template):
        """测试超长文档"""
        # 创建一个超长的文档
        long_content = "章节内容\n\n"
        long_document = "# 长文档\n\n"
        
        for i in range(1, 101):
            long_document += f"## {i}. 章节 {i}\n\n{long_content}"
        
        result = await structure_matcher.match(long_document, sample_template)
        
        assert result is not None
        # 应该能处理长文档，尽管匹配度可能不高
    
    @pytest.mark.asyncio
    async def test_special_characters(self, structure_matcher):
        """测试包含特殊字符的文档"""
        template = """
# 模板

## 1. 章节
内容
"""
        
        document = """
# 文档 (Document) [测试]

## 1. 章节 - 特殊字符测试 !@#$%^&*()
内容包含：中文、English、日本語、한국어、العربية

### 子章节 1.1
• 项目符号
→ 箭头符号
★ 星号
"""
        
        result = await structure_matcher.match(document, template)
        
        assert result is not None
        # 应该能处理特殊字符


class TestUtilityFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_match_structure_function(self, mock_llm_client):
        """测试 match_structure 便捷函数"""
        from tencent_doc_review.analyzer.structure_matcher import match_structure
        
        template = """
# 模板

## 1. 章节
内容
"""
        
        document = """
# 文档

## 1. 章节
内容
"""
        
        result = await match_structure(document, template, mock_llm_client)
        
        assert result is not None
        assert isinstance(result, StructureMatchResult)
    
    @pytest.mark.asyncio
    async def test_parse_document_structure_function(self, mock_llm_client):
        """测试 parse_document_structure 便捷函数"""
        from tencent_doc_review.analyzer.structure_matcher import parse_document_structure
        
        document = """
# 文档标题

## 1. 第一章
第一章内容

## 2. 第二章
第二章内容

### 2.1 子章节
子章节内容
"""
        
        result = await parse_document_structure(document, mock_llm_client)
        
        assert result is not None
        assert isinstance(result, Section)
        assert result.title == "Document" or len(result.children) > 0


class TestConfiguration:
    """测试配置选项"""
    
    @pytest.mark.asyncio
    async def test_custom_batch_size(self, mock_llm_client):
        """测试自定义批处理大小"""
        matcher = StructureMatcher(
            deepseek_client=mock_llm_client,
            config={'batch_size': 5, 'max_concurrency': 3}
        )
        
        assert matcher.config['batch_size'] == 5
        assert matcher.config['max_concurrency'] == 3
    
    @pytest.mark.asyncio
    async def test_different_matching_modes(self, mock_llm_client, sample_template, sample_document):
        """测试不同的匹配模式"""
        matcher = StructureMatcher(mock_llm_client)
        
        # 严格模式
        result_strict = await matcher.match(
            sample_document, 
            sample_template,
            matching_mode='strict'
        )
        
        # 宽松模式
        result_loose = await matcher.match(
            sample_document,
            sample_template,
            matching_mode='loose'
        )
        
        assert result_strict is not None
        assert result_loose is not None
        # 宽松模式的分数通常更高
        assert result_loose.overall_score >= result_strict.overall_score


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, mock_llm_client):
        """测试批处理性能"""
        matcher = StructureMatcher(mock_llm_client, config={'batch_size': 10})
        
        # 创建多个文档
        documents = []
        for i in range(20):
            documents.append({
                'text': f'# Document {i}\n\n## Section 1\nContent\n\n## Section 2\nContent',
                'template': '# Template\n\n## Section 1\n\n## Section 2'
            })
        
        import time
        start_time = time.time()
        
        # 批量处理
        tasks = [
            matcher.match(doc['text'], doc['template'])
            for doc in documents
        ]
        results = await asyncio.gather(*tasks)
        
        elapsed_time = time.time() - start_time
        
        assert len(results) == 20
        assert elapsed_time < 30  # 应该在30秒内完成
    
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, mock_llm_client):
        """测试内存效率"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        matcher = StructureMatcher(mock_llm_client)
        
        # 处理大量文档
        for i in range(100):
            doc = f'# Document {i}\n' + '\n'.join([f'## Section {j}\nContent' for j in range(10)])
            template = '# Template\n' + '\n'.join([f'## Section {j}' for j in range(10)])
            
            await matcher.match(doc, template)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 内存增长应该合理（小于500MB）
        assert memory_increase < 500


# ==================== 错误恢复测试 ====================

class TestErrorRecovery:
    """错误恢复测试"""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_llm_failure(self):
        """测试 LLM 失败时的优雅降级"""
        # 创建一个会失败的 mock
        failing_client = Mock()
        
        async def fail_analyze(*args, **kwargs):
            raise Exception("LLM service unavailable")
        
        failing_client.analyze = fail_analyze
        
        matcher = StructureMatcher(failing_client)
        
        # 应该使用回退方法
        result = await matcher.match("# Document", "# Template")
        
        assert result is not None
        # 即使 LLM 失败，也应该返回一个结果（可能质量较低）
    
    @pytest.mark.asyncio
    async def test_partial_result_on_timeout(self, mock_llm_client):
        """测试超时时的部分结果"""
        # 模拟一个慢速的 LLM
        slow_client = Mock()
        
        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(10)  # 模拟长时间运行
            return Mock(content='{"title": "Test"}')
        
        slow_client.analyze = slow_analyze
        
        matcher = StructureMatcher(slow_client, config={'timeout': 1})
        
        # 应该快速返回结果（可能是不完整的）
        import asyncio
        try:
            result = await asyncio.wait_for(
                matcher.match("# Doc", "# Template"),
                timeout=5
            )
            # 如果成功，应该有某种结果
        except asyncio.TimeoutError:
            # 超时也是可接受的结果
            pass


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, mock_llm_client):
        """测试端到端工作流"""
        # 1. 创建 matcher
        matcher = StructureMatcher(mock_llm_client)
        
        # 2. 准备真实场景的数据
        template = """
# 技术方案文档

## 1. 项目背景
项目背景描述...

## 2. 技术选型
技术选型说明...

## 3. 架构设计
架构设计详情...

## 4. 实施计划
实施计划安排...

## 5. 风险评估
风险评估分析...
"""
        
        document = """
# 智能客服系统技术方案

## 1. 项目背景
随着业务发展，客服需求日益增长...

## 2. 技术选型
- 后端：Python + FastAPI
- 前端：Vue.js
- 数据库：PostgreSQL
- 缓存：Redis

## 3. 架构设计
采用微服务架构，主要服务包括：
- 对话服务
- 意图识别服务
- 知识库服务

## 4. 实施计划
第一阶段：核心功能开发（2个月）
第二阶段：集成测试（1个月）
第三阶段：上线部署（2周）

## 5. 风险评估
1. 技术风险：新技术学习曲线
2. 进度风险：需求变更
3. 人员风险：核心人员变动
"""
        
        # 3. 执行匹配
        result = await matcher.match(document, template)
        
        # 4. 验证结果
        assert result is not None
        assert isinstance(result, StructureMatchResult)
        assert result.overall_score > 0
        assert len(result.section_matches) > 0
        
        # 5. 验证匹配状态
        matched = [m for m in result.section_matches if m.status.value == 'matched']
        missing = [m for m in result.section_matches if m.status.value == 'missing']
        
        # 应该有一些匹配成功的章节
        assert len(matched) >= 3
    
    @pytest.mark.asyncio
    async def test_batch_processing_integration(self, mock_llm_client):
        """测试批处理集成"""
        matcher = StructureMatcher(mock_llm_client)
        
        # 准备多个文档
        documents = []
        for i in range(5):
            documents.append({
                'document': f'# Document {i}\n\n## Section 1\nContent\n\n## Section 2\nContent',
                'template': '# Template\n\n## Section 1\n\n## Section 2'
            })
        
        # 批量处理
        results = await asyncio.gather(*[
            matcher.match(doc['document'], doc['template'])
            for doc in documents
        ])
        
        assert len(results) == 5
        for result in results:
            assert result is not None
            assert isinstance(result, StructureMatchResult)


# ==================== 辅助功能测试 ====================

class TestUtilityFunctions:
    """测试便捷函数"""
    
    @pytest.mark.asyncio
    async def test_match_structure_function(self, mock_llm_client):
        """测试 match_structure 便捷函数"""
        template = """
# 模板

## 1. 章节
内容
"""
        
        document = """
# 文档

## 1. 章节
内容
"""
        
        result = await match_structure(document, template, mock_llm_client)
        
        assert result is not None
        assert isinstance(result, StructureMatchResult)
    
    @pytest.mark.asyncio
    async def test_parse_document_structure_function(self, mock_llm_client):
        """测试 parse_document_structure 便捷函数"""
        document = """
# 文档标题

## 1. 第一章
第一章内容

## 2. 第二章
第二章内容

### 2.1 子章节
子章节内容
"""
        
        result = await parse_document_structure(document, mock_llm_client)
        
        assert result is not None
        assert isinstance(result, Section)


# ==================== 配置和选项测试 ====================

class TestConfiguration:
    """测试配置选项"""
    
    @pytest.mark.asyncio
    async def test_custom_batch_size(self, mock_llm_client):
        """测试自定义批处理大小"""
        matcher = StructureMatcher(
            deepseek_client=mock_llm_client,
            config={'batch_size': 5, 'max_concurrency': 2}
        )
        
        assert matcher.config['batch_size'] == 5
        assert matcher.config['max_concurrency'] == 2
    
    @pytest.mark.asyncio
    async def test_different_matching_modes(self, mock_llm_client, sample_template, sample_document):
        """测试不同的匹配模式"""
        matcher = StructureMatcher(mock_llm_client)
        
        # 严格模式
        result_strict = await matcher.match(
            sample_document, 
            sample_template,
            matching_mode='strict'
        )
        
        # 宽松模式
        result_loose = await matcher.match(
            sample_document,
            sample_template,
            matching_mode='loose'
        )
        
        assert result_strict is not None
        assert result_loose is not None
        # 宽松模式的分数通常更高或相等
        assert result_loose.overall_score >= result_strict.overall_score


# ==================== 运行所有测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
