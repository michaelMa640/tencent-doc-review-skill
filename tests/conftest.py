"""
测试配置和共享fixture

提供：
- 测试用的mock客户端
- 共享的测试数据
- 通用的fixture
"""

import pytest
import asyncio
from typing import Any, Dict, Generator
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass

# 确保可以导入src目录
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tencent_doc_review.deepseek_client import DeepSeekClient, LLMResponse, UsageInfo


# ==================== Mock 客户端 ====================

class MockDeepSeekClient(DeepSeekClient):
    """Mock DeepSeek客户端，用于测试"""
    
    def __init__(self, responses: dict = None):
        """
        初始化Mock客户端
        
        Args:
            responses: 预定义的响应字典，key是prompt类型，value是响应内容
        """
        self.responses = responses or {}
        self.call_count = 0
        self.last_prompt = None
    
    async def analyze(
        self,
        prompt: str,
        analysis_type: str = "general",
        **kwargs
    ) -> LLMResponse:
        """Mock分析方法"""
        self.call_count += 1
        self.last_prompt = prompt
        
        # 返回预定义的响应或默认响应
        content = self.responses.get(analysis_type, self._get_default_response(analysis_type))
        
        return LLMResponse(
            content=content,
            model="mock-model",
            usage=UsageInfo(prompt_tokens=100, completion_tokens=200, total_tokens=300)
        )
    
    def _get_default_response(self, analysis_type: str) -> str:
        """获取默认响应"""
        defaults = {
            "claim_extraction": """[
  {
    "text": "中国2023年GDP增长5.2%",
    "claim_type": "data",
    "confidence": 0.9,
    "needs_verification": true
  }
]""",
            "verification": """{
  "verification_status": "confirmed",
  "confidence": 0.95,
  "evidence": ["国家统计局官方数据"],
  "suggestion": "数据准确，无需修改"
}""",
            "structure": """{
  "sections": [
    {"title": "引言", "level": 1, "content": "..."},
    {"title": "正文", "level": 1, "content": "..."}
  ]
}""",
            "quality": """{
  "score": 85,
  "level": "good",
  "strengths": ["结构清晰", "逻辑连贯"],
  "weaknesses": ["数据支撑不足"],
  "suggestions": ["补充更多统计数据"]
}""",
        }
        return defaults.get(analysis_type, '{"status": "ok"}')


# ==================== 测试数据 ====================

@pytest.fixture
def sample_document() -> str:
    """示例文档内容"""
    return """
# 人工智能发展报告

## 引言

人工智能（AI）技术正在快速发展，深刻改变着各行各业。

## 市场规模

根据统计数据，2023年全球AI市场规模达到1500亿美元，预计到2025年将增长至2000亿美元。

## 应用领域

AI技术在医疗、金融、教育、制造等领域有广泛应用。

## 结论

AI技术发展前景广阔，但同时也面临数据安全、伦理等挑战。
"""


@pytest.fixture
def sample_template() -> str:
    """示例模板内容"""
    return """
# 报告模板

## 引言
- 背景介绍
- 目的和意义

## 主体
- 数据分析
- 案例研究
- 对比分析

## 结论
- 主要发现
- 建议
- 展望
"""


@pytest.fixture
def mock_deepseek_client() -> MockDeepSeekClient:
    """Mock DeepSeek 客户端"""
    return MockDeepSeekClient()


# ==================== 辅助函数 ====================

def assert_valid_analysis_result(result):
    """验证分析结果是否有效"""
    assert result is not None
    assert hasattr(result, 'document_id')
    assert hasattr(result, 'timestamp')
    assert hasattr(result, 'summary')


def create_test_document(text: str = "") -> Dict[str, Any]:
    """创建测试文档"""
    return {
        'id': f'test-doc-{hash(text) % 10000}',
        'title': 'Test Document',
        'text': text or 'This is a test document.',
        'context': {}
    }


# ==================== 配置 ====================

@pytest.fixture(scope="session")
def event_loop():
    """提供事件循环 fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# pytest 配置
def pytest_configure(config):
    """pytest 配置"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
