"""
事实核查模块

提供文章内容的自动化事实核查功能：
1. 从文本中提取需要验证的声明
2. 对关键信息进行联网搜索验证
3. 生成结构化核查结果
4. 提供可信度评估和修改建议

Usage:
    checker = FactChecker(deepseek_client, search_client)
    results = await checker.check(text, context)
    
    for result in results:
        print(f"{result.original_text}: {result.verification_status}")
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

from loguru import logger

from ..llm.base import LLMClient


class VerificationStatus(Enum):
    """验证状态枚举"""
    CONFIRMED = "confirmed"           # 已确认正确
    DISPUTED = "disputed"              # 存在争议
    UNVERIFIED = "unverified"          # 无法验证
    INCORRECT = "incorrect"            # 确认错误
    PARTIALLY_CORRECT = "partial"      # 部分正确


class ClaimType(Enum):
    """声明类型枚举"""
    DATA = "data"                      # 数据/统计
    DATE_TIME = "date_time"            # 时间/日期
    PERSON = "person"                  # 人物
    LOCATION = "location"              # 地点
    ORGANIZATION = "organization"      # 组织/机构
    EVENT = "event"                    # 事件
    QUOTATION = "quotation"            # 引用
    NUMBER = "number"                  # 数字/数量
    OTHER = "other"                    # 其他


@dataclass
class FactCheckResult:
    """
    事实核查结果数据类
    
    Attributes:
        id: 结果唯一标识
        original_text: 原文引用
        claim_type: 声明类型
        claim_content: 需要验证的具体内容
        verification_status: 验证状态
        confidence: 置信度 (0-1)
        evidence: 证据列表
        sources: 信息来源
        suggestion: 修改建议
        position: 在原文中的位置信息
        created_at: 创建时间
        verified_at: 验证时间
    """
    id: str = field(default_factory=lambda: f"fcr_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    original_text: str = ""
    claim_type: ClaimType = ClaimType.OTHER
    claim_content: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    suggestion: str = ""
    position: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "original_text": self.original_text,
            "claim_type": self.claim_type.value,
            "claim_content": self.claim_content,
            "verification_status": self.verification_status.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "sources": self.sources,
            "suggestion": self.suggestion,
            "position": self.position,
            "created_at": self.created_at,
            "verified_at": self.verified_at
        }
    
    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        status_emoji = {
            VerificationStatus.CONFIRMED: "✅",
            VerificationStatus.DISPUTED: "⚠️",
            VerificationStatus.UNVERIFIED: "❓",
            VerificationStatus.INCORRECT: "❌",
            VerificationStatus.PARTIALLY_CORRECT: "〽️"
        }
        
        emoji = status_emoji.get(self.verification_status, "❓")
        
        md = f"""### {emoji} {self.claim_type.value.upper()}: {self.verification_status.value}

**原文**: {self.original_text}

**验证内容**: {self.claim_content}

**置信度**: {self.confidence:.1%}

**证据**:
"""
        for i, ev in enumerate(self.evidence, 1):
            md += f"{i}. {ev}\n"
        
        if self.sources:
            md += "\n**来源**:\n"
            for src in self.sources:
                md += f"- [{src.get('title', 'Link')}]({src.get('url', '')})\n"
        
        md += f"\n**建议**: {self.suggestion}\n\n---\n"
        
        return md


@dataclass
class Claim:
    """
    从文本中提取的需要验证的声明
    
    Attributes:
        text: 声明文本
        type: 声明类型
        entities: 提取的实体（人名、地名等）
        position: 在原文中的位置
        context: 上下文信息
    """
    text: str
    type: ClaimType
    entities: List[Dict[str, Any]] = field(default_factory=list)
    position: Dict[str, Any] = field(default_factory=dict)
    context: str = ""


class SearchClient:
    """
    联网搜索客户端（预留接口）
    
    用于验证关键信息，当前为占位实现。
    后续可集成：
    - Google Search API
    - Bing Search API
    - Serper API
    - 其他搜索引擎
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.enabled = False  # 默认禁用，需要配置 API Key 后启用
        logger.info("SearchClient initialized (placeholder mode)")
    
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        执行搜索查询
        
        Args:
            query: 搜索关键词
            num_results: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if not self.enabled:
            logger.warning("SearchClient is not enabled. Please configure API key.")
            return []
        
        # TODO: 实现实际的搜索逻辑
        # 这里返回模拟数据用于测试
        return [
            {
                "title": f"Search result for: {query}",
                "url": "https://example.com/result",
                "snippet": "This is a placeholder search result.",
                "source": "placeholder"
            }
        ]
    
    async def verify_fact(self, claim: str, context: str = "") -> Dict[str, Any]:
        """
        验证具体事实声明
        
        Args:
            claim: 需要验证的声明
            context: 上下文信息
            
        Returns:
            验证结果
        """
        search_results = await self.search(claim)
        
        # 简化处理：基于搜索结果数量判断
        if len(search_results) > 0:
            return {
                "status": "partially_verified",
                "confidence": 0.5,
                "sources": search_results[:3],
                "note": "Placeholder verification - configure real search API for accurate results"
            }
        else:
            return {
                "status": "unverified",
                "confidence": 0.0,
                "sources": [],
                "note": "Search not available"
            }


class FactChecker:
    """
    事实核查器主类
    
    提供完整的事实核查流程：
    1. 从文本中提取声明
    2. 对声明进行分类
    3. 使用搜索验证（可选）
    4. 生成结构化核查结果
    
    Usage:
        checker = FactChecker(deepseek_client, search_client)
        
        # 完整核查流程
        results = await checker.check(text, context)
        
        # 仅提取声明（不验证）
        claims = await checker.extract_claims(text)
        
        # 验证单个声明
        result = await checker.verify_claim(claim, context)
    """
    
    def __init__(
        self,
        deepseek_client: LLMClient,
        search_client: Optional[SearchClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化事实核查器
        
        Args:
            deepseek_client: DeepSeek API 客户端（必需）
            search_client: 搜索客户端（可选，用于验证）
            config: 配置参数
        """
        self.llm = deepseek_client
        self.search = search_client or SearchClient()  # 使用占位实现
        self.config = config or {}
        
        # 可配置参数
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.max_claims = self.config.get("max_claims", 50)
        self.enable_search = self.config.get("enable_search", False)
        
        logger.info(f"FactChecker initialized (search_enabled={self.enable_search})")
    
    async def check(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[FactCheckResult]:
        """
        执行完整的事实核查流程
        
        Args:
            text: 需要核查的文本
            context: 上下文信息（如文章主题、来源等）
            
        Returns:
            核查结果列表
        """
        logger.info(f"Starting fact check for text ({len(text)} chars)")
        
        # Step 1: 提取声明
        claims = await self.extract_claims(text, context)
        logger.info(f"Extracted {len(claims)} claims")
        
        if not claims:
            logger.warning("No claims extracted from text")
            return []
        
        # Step 2: 验证每个声明
        results = []
        for i, claim in enumerate(claims[:self.max_claims]):
            logger.debug(f"Verifying claim {i+1}/{len(claims)}: {claim.text[:50]}...")
            
            try:
                result = await self.verify_claim(claim, context)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to verify claim: {e}")
                # 添加错误标记的结果
                results.append(FactCheckResult(
                    original_text=claim.text,
                    claim_type=claim.type,
                    claim_content=claim.text,
                    verification_status=VerificationStatus.UNVERIFIED,
                    confidence=0.0,
                    suggestion=f"Verification failed: {str(e)}"
                ))
        
        logger.info(f"Fact check completed: {len(results)} results")
        return results
    
    async def extract_claims(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Claim]:
        """
        从文本中提取需要验证的声明
        
        使用 LLM 分析文本，识别关键信息点。
        
        Args:
            text: 输入文本
            context: 上下文信息
            
        Returns:
            声明列表
        """
        # 构建提示词
        prompt = self._build_extraction_prompt(text, context)
        
        # 调用 LLM
        try:
            analysis = await self.llm.analyze(prompt, analysis_type="fact_check")
            content = analysis.content if hasattr(analysis, 'content') else str(analysis)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return []
        
        # 解析结果
        claims = self._parse_claims_from_response(content, text)
        return claims
    
    def _build_extraction_prompt(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建声明提取提示词"""
        
        context_str = ""
        if context:
            context_str = f"\n上下文信息：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        
        prompt = f"""请仔细分析以下文本，提取所有需要事实核查的关键信息。

文本内容：
{text}
{context_str}

请识别以下类型的信息：
1. **数据/统计** - 具体数字、百分比、统计数据等
2. **时间/日期** - 具体时间点、时间段、年份等
3. **人物** - 人名、职务、身份等
4. **地点** - 地名、位置、区域等
5. **组织** - 机构、公司、政府部门等
6. **事件** - 具体事件描述、历史事实等
7. **引用** - 引用他人言论、文献等

请以 JSON 格式输出，格式如下：
```json
{{
  "claims": [
    {{
      "text": "原文引用",
      "type": "数据/时间/人物/地点/组织/事件/引用/其他",
      "claim": "需要验证的具体内容",
      "entities": ["提取的实体"],
      "context": "上下文信息"
    }}
  ]
}}
```

注意：
- 只输出 JSON，不要有其他说明文字
- 确保每个 claim 都包含完整的原文引用
- type 必须从指定的类型中选择
- 如果没有需要验证的内容，返回空数组
"""
        return prompt
    
    def _parse_claims_from_response(
        self,
        response: str,
        original_text: str
    ) -> List[Claim]:
        """从 LLM 响应中解析声明列表"""
        
        claims = []
        
        try:
            # 提取 JSON 部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in LLM response")
                return []
            
            data = json.loads(json_match.group())
            
            if "claims" not in data or not isinstance(data["claims"], list):
                logger.warning("Invalid JSON structure: missing 'claims' array")
                return []
            
            for item in data["claims"]:
                try:
                    # 映射类型
                    type_str = item.get("type", "其他").upper()
                    claim_type = self._map_claim_type(type_str)
                    
                    # 创建 Claim 对象
                    claim = Claim(
                        text=item.get("text", ""),
                        type=claim_type,
                        entities=item.get("entities", []),
                        position=self._find_position(item.get("text", ""), original_text),
                        context=item.get("context", "")
                    )
                    
                    claims.append(claim)
                    
                except Exception as e:
                    logger.error(f"Failed to parse claim item: {e}")
                    continue
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing claims: {e}")
        
        logger.info(f"Parsed {len(claims)} claims from LLM response")
        return claims
    
    def _map_claim_type(self, type_str: str) -> ClaimType:
        """将字符串映射到 ClaimType"""
        type_mapping = {
            "数据": ClaimType.DATA,
            "DATA": ClaimType.DATA,
            "时间": ClaimType.DATE_TIME,
            "DATE_TIME": ClaimType.DATE_TIME,
            "日期": ClaimType.DATE_TIME,
            "人物": ClaimType.PERSON,
            "PERSON": ClaimType.PERSON,
            "人名": ClaimType.PERSON,
            "地点": ClaimType.LOCATION,
            "LOCATION": ClaimType.LOCATION,
            "地名": ClaimType.LOCATION,
            "组织": ClaimType.ORGANIZATION,
            "ORGANIZATION": ClaimType.ORGANIZATION,
            "机构": ClaimType.ORGANIZATION,
            "事件": ClaimType.EVENT,
            "EVENT": ClaimType.EVENT,
            "引用": ClaimType.QUOTATION,
            "QUOTATION": ClaimType.QUOTATION,
            "其他": ClaimType.OTHER,
            "OTHER": ClaimType.OTHER,
        }
        return type_mapping.get(type_str.upper(), ClaimType.OTHER)
    
    def _find_position(self, text: str, original: str) -> Dict[str, Any]:
        """在原文中查找文本位置"""
        if not text or not original:
            return {}
        
        try:
            start = original.find(text)
            if start == -1:
                # 尝试模糊匹配
                return {"search_text": text[:50], "note": "Exact match not found"}
            
            end = start + len(text)
            
            # 计算段落和行号
            paragraphs_before = original[:start].count('\n\n') + 1
            lines_before = original[:start].count('\n') + 1
            
            return {
                "start": start,
                "end": end,
                "length": len(text),
                "paragraph": paragraphs_before,
                "line": lines_before,
                "excerpt": original[max(0, start-20):min(len(original), end+20)]
            }
            
        except Exception as e:
            logger.error(f"Error finding position: {e}")
            return {"error": str(e)}
    
    async def verify_claim(
        self,
        claim: Claim,
        context: Optional[Dict[str, Any]] = None
    ) -> FactCheckResult:
        """
        验证单个声明
        
        Args:
            claim: 要验证的声明
            context: 上下文信息
            
        Returns:
            核查结果
        """
        logger.debug(f"Verifying claim: {claim.text[:50]}...")
        
        # 构建验证提示
        prompt = self._build_verification_prompt(claim, context)
        
        # 调用 LLM 进行验证
        try:
            analysis = await self.llm.analyze(prompt, analysis_type="fact_check")
            llm_result = analysis.content if hasattr(analysis, 'content') else str(analysis)
        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            return self._create_error_result(claim, f"LLM error: {e}")
        
        # 解析 LLM 结果
        parsed_result = self._parse_verification_result(llm_result, claim)
        
        # 如果启用了搜索，进行交叉验证
        if self.enable_search and self.search.enabled:
            search_result = await self._cross_verify_with_search(claim, parsed_result)
            parsed_result = self._merge_verification_results(parsed_result, search_result)
        
        # 创建最终结果
        result = FactCheckResult(
            original_text=claim.text,
            claim_type=claim.type,
            claim_content=parsed_result.get("claim_content", claim.text),
            verification_status=VerificationStatus(parsed_result.get("status", "unverified")),
            confidence=parsed_result.get("confidence", 0.0),
            evidence=parsed_result.get("evidence", []),
            sources=parsed_result.get("sources", []),
            suggestion=parsed_result.get("suggestion", ""),
            position=claim.position,
            verified_at=datetime.now().isoformat()
        )
        
        logger.debug(f"Verification completed: {result.verification_status.value}")
        return result
    
    def _build_verification_prompt(
        self,
        claim: Claim,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建验证提示词"""
        
        context_str = ""
        if context:
            context_str = f"\n上下文信息：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        
        type_guidance = {
            ClaimType.DATA: "这是一个数据声明，请核实数字的准确性、数据来源和统计口径。",
            ClaimType.DATE_TIME: "这是一个时间声明，请核实具体日期、时间范围是否正确。",
            ClaimType.PERSON: "这是一个人物声明，请核实人物身份、职务等信息。",
            ClaimType.LOCATION: "这是一个地点声明，请核实地理位置、行政区划是否正确。",
            ClaimType.ORGANIZATION: "这是一个组织声明，请核实机构名称、性质等信息。",
            ClaimType.EVENT: "这是一个事件声明，请核实事件经过、参与方等信息。",
            ClaimType.QUOTATION: "这是一个引用声明，请核实引用来源、上下文是否准确。",
        }
        
        type_guidance_str = type_guidance.get(claim.type, "请核实该声明的准确性。")
        
        prompt = f"""请对以下声明进行事实核查：

**声明类型**: {claim.type.value}
**声明原文**: {claim.text}
**实体信息**: {json.dumps(claim.entities, ensure_ascii=False)}
{type_guidance_str}
{context_str}

请按照以下格式输出核查结果：

```json
{{
  "claim_content": "需要验证的核心内容",
  "status": "confirmed/disputed/unverified/incorrect/partial",
  "confidence": 0.85,
  "evidence": [
    "证据1: 具体说明",
    "证据2: 具体说明"
  ],
  "sources": [
    {{
      "title": "来源名称",
      "url": "https://example.com",
      "type": "official/media/academic/other"
    }}
  ],
  "suggestion": "如果存在问题，给出具体的修改建议"
}}
```

注意：
1. status 必须是以下之一：confirmed(已确认), disputed(存在争议), unverified(无法验证), incorrect(确认错误), partial(部分正确)
2. confidence 是 0-1 之间的浮点数
3. 尽可能提供具体的证据和可靠的来源
4. 如果无法验证，说明原因
5. 只输出 JSON，不要有其他说明文字
"""
        return prompt
    
    def _parse_verification_result(
        self,
        llm_output: str,
        claim: Claim
    ) -> Dict[str, Any]:
        """解析 LLM 验证结果"""
        
        try:
            # 提取 JSON
            json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in LLM output")
                return self._create_default_result(claim)
            
            result = json.loads(json_match.group())
            
            # 验证必要字段
            if "status" not in result:
                result["status"] = "unverified"
            if "confidence" not in result:
                result["confidence"] = 0.0
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return self._create_default_result(claim)
        except Exception as e:
            logger.error(f"Unexpected error parsing result: {e}")
            return self._create_default_result(claim)
    
    def _create_default_result(self, claim: Claim) -> Dict[str, Any]:
        """创建默认结果"""
        return {
            "claim_content": claim.text,
            "status": "unverified",
            "confidence": 0.0,
            "evidence": [],
            "sources": [],
            "suggestion": "无法自动验证，请人工核实"
        }
    
    def _create_error_result(self, claim: Claim, error_msg: str) -> FactCheckResult:
        """创建错误结果"""
        return FactCheckResult(
            original_text=claim.text,
            claim_type=claim.type,
            claim_content=claim.text,
            verification_status=VerificationStatus.UNVERIFIED,
            confidence=0.0,
            evidence=[],
            sources=[],
            suggestion=f"验证过程出错: {error_msg}",
            position=claim.position
        )
    
    async def _cross_verify_with_search(
        self,
        claim: Claim,
        llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用搜索进行交叉验证
        
        Args:
            claim: 声明
            llm_result: LLM 验证结果
            
        Returns:
            搜索结果
        """
        if not self.search or not self.search.enabled:
            return {}
        
        try:
            search_result = await self.search.verify_fact(
                claim=claim.text,
                context=f"Type: {claim.type.value}, Entities: {claim.entities}"
            )
            return search_result
        except Exception as e:
            logger.error(f"Search verification failed: {e}")
            return {}
    
    def _merge_verification_results(
        self,
        llm_result: Dict[str, Any],
        search_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并 LLM 和搜索验证结果
        
        Args:
            llm_result: LLM 结果
            search_result: 搜索结果
            
        Returns:
            合并后的结果
        """
        if not search_result:
            return llm_result
        
        # 简单的合并策略：优先使用 LLM 结果，搜索作为补充
        merged = llm_result.copy()
        
        # 如果搜索有更高置信度，更新置信度
        if search_result.get("confidence", 0) > merged.get("confidence", 0):
            merged["confidence"] = search_result["confidence"]
        
        # 合并来源
        if "sources" in search_result and search_result["sources"]:
            merged.setdefault("sources", []).extend(search_result["sources"])
        
        return merged
    
    async def batch_check(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
        max_concurrency: int = 3
    ) -> List[List[FactCheckResult]]:
        """
        批量核查多个文本
        
        Args:
            texts: 文本列表
            context: 上下文
            max_concurrency: 最大并发数
            
        Returns:
            每组文本的核查结果
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def check_with_limit(text: str) -> List[FactCheckResult]:
            async with semaphore:
                return await self.check(text, context)
        
        tasks = [check_with_limit(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch check error: {result}")
                final_results.append([])
            else:
                final_results.append(result)
        
        return final_results


# 便捷函数

async def check_facts(
    text: str,
    deepseek_client: LLMClient,
    search_client: Optional[SearchClient] = None,
    context: Optional[Dict[str, Any]] = None
) -> List[FactCheckResult]:
    """
    便捷函数：快速核查文本事实
    
    Args:
        text: 需要核查的文本
        deepseek_client: DeepSeek 客户端
        search_client: 搜索客户端（可选）
        context: 上下文
        
    Returns:
        核查结果列表
    """
    checker = FactChecker(
        deepseek_client=deepseek_client,
        search_client=search_client
    )
    
    try:
        return await checker.check(text, context)
    finally:
        # 清理资源
        pass


async def extract_claims_only(
    text: str,
    deepseek_client: LLMClient
) -> List[Claim]:
    """
    便捷函数：仅提取声明，不验证
    
    Args:
        text: 输入文本
        deepseek_client: DeepSeek 客户端
        
    Returns:
        声明列表
    """
    checker = FactChecker(deepseek_client=deepseek_client)
    return await checker.extract_claims(text)
