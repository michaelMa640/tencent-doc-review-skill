"""
性能测试

测试系统在各种负载下的性能表现，包括：
- 大文档处理性能
- 并发处理能力
- 内存使用效率
- 响应时间
"""

import pytest
import asyncio
import time
import psutil
import os
from typing import List, Dict, Any
from unittest.mock import Mock

from tencent_doc_review.analyzer.document_analyzer import (
    DocumentAnalyzer,
    AnalysisConfig,
    AnalysisType
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端 - 模拟真实延迟"""
    client = Mock()
    
    async def mock_analyze(prompt, **kwargs):
        # 模拟真实 API 调用延迟 (100-500ms)
        await asyncio.sleep(0.1 + (hash(prompt) % 400) / 1000)
        
        # 返回简化的响应
        return Mock(content='{"status": "ok", "result": "test"}')
    
    client.analyze = mock_analyze
    return client


@pytest.fixture
def performance_analyzer(mock_llm_client):
    """创建用于性能测试的 DocumentAnalyzer 实例"""
    return DocumentAnalyzer(
        deepseek_client=mock_llm_client,
        config={'batch_size': 5, 'max_concurrency': 3}
    )


@pytest.fixture
def small_document():
    """小文档 (约1KB)"""
    return """# 小文档

## 1. 概述
这是一个小文档，用于测试小文档处理性能。

## 2. 内容
这里是一些内容。"""


@pytest.fixture
def medium_document():
    """中等文档 (约10KB)"""
    content = "# 中等文档\n\n"
    for i in range(1, 21):
        content += f"## {i}. 章节 {i}\n\n"
        content += "这是章节内容。" * 50 + "\n\n"
    return content


@pytest.fixture
def large_document():
    """大文档 (约100KB)"""
    content = "# 大文档\n\n"
    for i in range(1, 101):
        content += f"## {i}. 章节 {i}\n\n"
        content += "这是章节内容。" * 100 + "\n\n"
    return content


# ==================== 性能测试类 ====================

class TestDocumentSizePerformance:
    """测试不同大小文档的处理性能"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_small_document_performance(self, performance_analyzer, small_document):
        """测试小文档处理性能（应该在1秒内完成）"""
        start_time = time.time()
        
        result = await performance_analyzer.analyze(
            document_text=small_document,
            document_id="perf-test-small"
        )
        
        elapsed_time = time.time() - start_time
        
        assert result is not None
        assert elapsed_time < 5.0, f"小文档处理太慢: {elapsed_time:.2f}秒"
        print(f"小文档处理时间: {elapsed_time:.2f}秒")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_medium_document_performance(self, performance_analyzer, medium_document):
        """测试中等文档处理性能（应该在10秒内完成）"""
        start_time = time.time()
        
        result = await performance_analyzer.analyze(
            document_text=medium_document,
            document_id="perf-test-medium"
        )
        
        elapsed_time = time.time() - start_time
        
        assert result is not None
        assert elapsed_time < 30.0, f"中等文档处理太慢: {elapsed_time:.2f}秒"
        print(f"中等文档处理时间: {elapsed_time:.2f}秒")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_large_document_performance(self, performance_analyzer, large_document):
        """测试大文档处理性能（应该在60秒内完成）"""
        start_time = time.time()
        
        result = await performance_analyzer.analyze(
            document_text=large_document,
            document_id="perf-test-large"
        )
        
        elapsed_time = time.time() - start_time
        
        assert result is not None
        assert elapsed_time < 90.0, f"大文档处理太慢: {elapsed_time:.2f}秒"
        print(f"大文档处理时间: {elapsed_time:.2f}秒")


class TestConcurrencyPerformance:
    """测试并发处理性能"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_concurrent_analysis(self, performance_analyzer, small_document):
        """测试并发分析性能"""
        num_tasks = 5
        
        # 创建多个并发任务
        tasks = [
            performance_analyzer.analyze(
                document_text=small_document,
                document_id=f"concurrent-test-{i}"
            )
            for i in range(num_tasks)
        ]
        
        start_time = time.time()
        
        # 并发执行
        results = await asyncio.gather(*tasks)
        
        elapsed_time = time.time() - start_time
        
        # 验证所有任务完成
        assert len(results) == num_tasks
        for result in results:
            assert result is not None
            assert isinstance(result, type(results[0]))
        
        # 并发应该比串行快
        print(f"并发处理 {num_tasks} 个文档耗时: {elapsed_time:.2f}秒")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_batch_processing_performance(self, performance_analyzer, small_document):
        """测试批量处理性能"""
        documents = [
            {
                'text': small_document,
                'id': f'batch-test-{i}',
                'title': f'Batch Document {i}'
            }
            for i in range(10)
        ]
        
        progress_updates = []
        
        def progress_callback(current, total, message):
            progress_updates.append({
                'current': current,
                'total': total,
                'message': message
            })
        
        start_time = time.time()
        
        results = await performance_analyzer.analyze_batch(
            documents=documents,
            progress_callback=progress_callback
        )
        
        elapsed_time = time.time() - start_time
        
        assert len(results) == 10
        assert len(progress_updates) > 0
        
        print(f"批量处理 10 个文档耗时: {elapsed_time:.2f}秒")
        print(f"收到 {len(progress_updates)} 次进度更新")


class TestMemoryUsage:
    """测试内存使用"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_memory_usage_with_large_documents(self, performance_analyzer, large_document):
        """测试大文档处理时的内存使用"""
        process = psutil.Process(os.getpid())
        
        # 记录初始内存
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 处理多个大文档
        for i in range(3):
            result = await performance_analyzer.analyze(
                document_text=large_document,
                document_id=f"memory-test-{i}"
            )
            assert result is not None
        
        # 记录最终内存
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"初始内存: {initial_memory:.2f} MB")
        print(f"最终内存: {final_memory:.2f} MB")
        print(f"内存增长: {memory_increase:.2f} MB")
        
        # 内存增长应该合理（小于500MB）
        assert memory_increase < 500, f"内存增长过大: {memory_increase:.2f} MB"


# ==================== 运行所有测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
