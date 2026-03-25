"""
质量评估模块

提供文章质量的多维度评估功能：
1. 内容完整性评估
2. 逻辑清晰度评估
3. 论证充分性评估
4. 数据准确性评估
5. 语言表达评估
6. 格式规范评估

输出：总体评分 + 维度评分 + 改进建议

Usage:
    evaluator = QualityEvaluator(deepseek_client)
    
    # 完整质量评估
    report = await evaluator.evaluate(text, context)
    
    # 快速评分
    score = await evaluator.quick_score(text)
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from loguru import logger

from ..deepseek_client import DeepSeekClient


class QualityDimension(Enum):
    """质量评估维度枚举"""
    COMPLETENESS = "completeness"           # 内容完整性
    CLARITY = "clarity"                     # 逻辑清晰度
    ARGUMENTATION = "argumentation"         # 论证充分性
    DATA_ACCURACY = "data_accuracy"         # 数据准确性
    LANGUAGE = "language"                   # 语言表达
    FORMAT = "format"                       # 格式规范
    OVERALL = "overall"                     # 总体评估


class QualityLevel(Enum):
    """质量等级枚举"""
    EXCELLENT = "excellent"                 # 优秀 (90-100)
    GOOD = "good"                           # 良好 (80-89)
    SATISFACTORY = "satisfactory"           # 合格 (70-79)
    NEEDS_IMPROVEMENT = "needs_improvement" # 待改进 (60-69)
    POOR = "poor"                           # 不合格 (<60)


@dataclass
class DimensionScore:
    """
    单个维度评分
    
    Attributes:
        dimension: 评估维度
        score: 分数 (0-100)
        weight: 权重
        level: 质量等级
        strengths: 优点列表
        weaknesses: 不足列表
        suggestions: 改进建议
    """
    dimension: QualityDimension
    score: float = 0.0
    weight: float = 1.0
    level: QualityLevel = QualityLevel.POOR
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level.value,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions
        }


@dataclass
class QualityReport:
    """
    质量评估完整报告
    
    Attributes:
        overall_score: 总体分数
        overall_level: 总体等级
        dimension_scores: 各维度评分列表
        weighted_average: 加权平均分
        summary: 评估摘要
        detailed_analysis: 详细分析
        priority_improvements: 优先改进项
        created_at: 创建时间
        metadata: 元数据
    """
    overall_score: float = 0.0
    overall_level: QualityLevel = QualityLevel.POOR
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    weighted_average: float = 0.0
    summary: str = ""
    detailed_analysis: str = ""
    priority_improvements: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "overall_score": round(self.overall_score, 2),
            "overall_level": self.overall_level.value,
            "dimension_scores": [ds.to_dict() for ds in self.dimension_scores],
            "weighted_average": round(self.weighted_average, 2),
            "summary": self.summary,
            "detailed_analysis": self.detailed_analysis,
            "priority_improvements": self.priority_improvements,
            "created_at": self.created_at,
            "metadata": self.metadata
        }
    
    def to_markdown(self) -> str:
        """转换为 Markdown 报告"""
        level_icons = {
            QualityLevel.EXCELLENT: "🌟",
            QualityLevel.GOOD: "✅",
            QualityLevel.SATISFACTORY: "👍",
            QualityLevel.NEEDS_IMPROVEMENT: "⚠️",
            QualityLevel.POOR: "❌"
        }
        
        icon = level_icons.get(self.overall_level, "❓")
        
        md = f"""# 质量评估报告 {icon}

**评估时间**: {self.created_at}
**总体评分**: {self.overall_score:.1f}/100
**质量等级**: {self.overall_level.value.upper()}

## 评分概览

| 维度 | 得分 | 等级 | 权重 |
|------|------|------|------|
"""
        
        for ds in self.dimension_scores:
            level_str = ds.level.value
            md += f"| {ds.dimension.value} | {ds.score:.1f} | {level_str} | {ds.weight} |\n"
        
        md += f"""
**加权平均分**: {self.weighted_average:.1f}

## 评估摘要

{self.summary}

## 各维度详细分析

"""
        
        for ds in self.dimension_scores:
            md += f"""### {ds.dimension.value.upper()} ({ds.score:.1f}/100)

**等级**: {ds.level.value}

**优点**:
"""
            if ds.strengths:
                for strength in ds.strengths:
                    md += f"- {strength}\n"
            else:
                md += "- 暂无突出优点\n"
            
            md += "\n**不足**:\n"
            if ds.weaknesses:
                for weakness in ds.weaknesses:
                    md += f"- {weakness}\n"
            else:
                md += "- 无明显不足\n"
            
            md += "\n**改进建议**:\n"
            if ds.suggestions:
                for suggestion in ds.suggestions:
                    md += f"- {suggestion}\n"
            else:
                md += "- 保持当前水平\n"
            
            md += "\n---\n\n"
        
        md += """## 优先改进项

"""
        if self.priority_improvements:
            for i, item in enumerate(self.priority_improvements, 1):
                md += f"{i}. {item}\n"
        else:
            md += "当前无明显需要优先改进的项。\n"
        
        md += f"""

---
*报告生成时间: {self.created_at}*
"""
        
        return md


class QualityEvaluator:
    """
    质量评估器主类
    
    提供文章质量的多维度评估功能。
    
    Usage:
        evaluator = QualityEvaluator(deepseek_client)
        
        # 完整质量评估
        report = await evaluator.evaluate(text, context)
        
        # 快速评分
        score = await evaluator.quick_score(text)
        
        # 单维度评估
        dimension_score = await evaluator.evaluate_dimension(
            text,
            QualityDimension.COMPLETENESS
        )
    """
    
    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化质量评估器
        
        Args:
            deepseek_client: DeepSeek API 客户端
            config: 配置参数
        """
        self.llm = deepseek_client
        self.config = config or {}
        
        # 可配置参数
        self.default_weights = self.config.get("default_weights", {
            QualityDimension.COMPLETENESS: 0.20,
            QualityDimension.CLARITY: 0.15,
            QualityDimension.ARGUMENTATION: 0.15,
            QualityDimension.DATA_ACCURACY: 0.15,
            QualityDimension.LANGUAGE: 0.15,
            QualityDimension.FORMAT: 0.10,
        })
        
        self.score_thresholds = self.config.get("score_thresholds", {
            QualityLevel.EXCELLENT: 90,
            QualityLevel.GOOD: 80,
            QualityLevel.SATISFACTORY: 70,
            QualityLevel.NEEDS_IMPROVEMENT: 60,
            QualityLevel.POOR: 0,
        })
        
        logger.info("QualityEvaluator initialized")
    
    async def evaluate(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        dimensions: Optional[List[QualityDimension]] = None
    ) -> QualityReport:
        """
        执行完整的质量评估
        
        这是主要入口方法，执行多维度质量评估。
        
        Args:
            text: 待评估文本
            context: 上下文信息（如文章类型、目标读者等）
            dimensions: 指定评估维度（None=所有维度）
            
        Returns:
            完整质量评估报告
        """
        logger.info(f"Starting quality evaluation ({len(text)} chars)")
        
        # 确定评估维度
        if dimensions is None:
            dimensions = [
                QualityDimension.COMPLETENESS,
                QualityDimension.CLARITY,
                QualityDimension.ARGUMENTATION,
                QualityDimension.DATA_ACCURACY,
                QualityDimension.LANGUAGE,
                QualityDimension.FORMAT,
            ]
        
        # 评估各维度
        dimension_scores = []
        for dimension in dimensions:
            try:
                score = await self.evaluate_dimension(text, dimension, context)
                dimension_scores.append(score)
                logger.debug(f"Dimension {dimension.value}: {score.score:.1f}")
            except Exception as e:
                logger.error(f"Failed to evaluate dimension {dimension.value}: {e}")
                # 添加错误标记的评分
                dimension_scores.append(DimensionScore(
                    dimension=dimension,
                    score=0.0,
                    level=QualityLevel.POOR,
                    weaknesses=[f"评估失败: {str(e)}"]
                ))
        
        # 计算加权平均分
        weighted_average = self._calculate_weighted_average(dimension_scores)
        
        # 确定总体等级
        overall_level = self._determine_quality_level(weighted_average)
        
        # 生成摘要
        summary = self._generate_evaluation_summary(
            dimension_scores,
            weighted_average
        )
        
        # 生成详细分析
        detailed_analysis = self._generate_detailed_analysis(dimension_scores)
        
        # 提取优先改进项
        priority_improvements = self._extract_priority_improvements(dimension_scores)
        
        # 创建报告
        report = QualityReport(
            overall_score=weighted_average,
            overall_level=overall_level,
            dimension_scores=dimension_scores,
            weighted_average=weighted_average,
            summary=summary,
            detailed_analysis=detailed_analysis,
            priority_improvements=priority_improvements,
            metadata={
                "text_length": len(text),
                "evaluated_dimensions": [d.value for d in dimensions],
                "evaluation_version": "1.0"
            }
        )
        
        logger.info(f"Quality evaluation completed: {weighted_average:.1f}/100 ({overall_level.value})")
        return report
    
    async def evaluate_dimension(
        self,
        text: str,
        dimension: QualityDimension,
        context: Optional[Dict[str, Any]] = None
    ) -> DimensionScore:
        """
        评估单个维度
        
        Args:
            text: 待评估文本
            dimension: 评估维度
            context: 上下文
            
        Returns:
            维度评分
        """
        # 构建评估提示
        prompt = self._build_dimension_prompt(text, dimension, context)
        
        # 调用 LLM 评估
        try:
            analysis = await self.llm.analyze(prompt, analysis_type="quality")
            content = analysis.content if hasattr(analysis, 'content') else str(analysis)
        except Exception as e:
            logger.error(f"LLM evaluation failed for dimension {dimension.value}: {e}")
            return self._create_error_dimension_score(dimension, str(e))
        
        # 解析评估结果
        return self._parse_dimension_result(content, dimension)
    
    async def quick_score(self, text: str) -> float:
        """
        快速评分
        
        返回总体质量分数，不生成详细报告。
        
        Args:
            text: 待评估文本
            
        Returns:
            质量分数 (0-100)
        """
        prompt = f"""请对以下文本进行快速质量评估，只输出一个总分（0-100）：

文本内容：
{text[:2000]}  # 只取前2000字符

请只回复一个数字，表示总体质量分数（0-100）。
"""
        
        try:
            analysis = await self.llm.analyze(prompt)
            content = analysis.content if hasattr(analysis, 'content') else str(analysis)
            
            # 提取数字
            import re
            numbers = re.findall(r'\d+', content)
            if numbers:
                score = int(numbers[0])
                return min(100, max(0, score))
            
            return 50.0  # 默认值
            
        except Exception as e:
            logger.error(f"Quick score failed: {e}")
            return 0.0
    
    # ==================== 辅助方法 ====================
    
    def _build_dimension_prompt(
        self,
        text: str,
        dimension: QualityDimension,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建维度评估提示词"""
        
        dimension_prompts = {
            QualityDimension.COMPLETENESS: """评估内容完整性：
- 是否包含所有必要部分（引言、正文、结论等）
- 每个部分是否完整，没有明显缺失
- 论证是否完整，没有跳跃或遗漏
- 数据、引用、参考文献是否齐全""",
            
            QualityDimension.CLARITY: """评估逻辑清晰度：
- 整体结构是否清晰合理
- 段落之间逻辑是否连贯
- 论证过程是否清晰易懂
- 是否有明确的主题句和结论句""",
            
            QualityDimension.ARGUMENTATION: """评估论证充分性：
- 论点是否明确、有说服力
- 论据是否充分、相关
- 论证方法是否得当
- 是否考虑了反方观点""",
            
            QualityDimension.DATA_ACCURACY: """评估数据准确性：
- 数据是否准确、可靠
- 数据来源是否可信
- 统计方法是否正确
- 数据呈现是否清晰""",
            
            QualityDimension.LANGUAGE: """评估语言表达：
- 用词是否准确、恰当
- 句式是否多样、流畅
- 语气是否得当
- 是否有语法、拼写错误""",
            
            QualityDimension.FORMAT: """评估格式规范：
- 是否符合要求的格式规范
- 标题、段落格式是否统一
- 引用格式是否正确
- 整体排版是否美观""",
        }
        
        dimension_desc = dimension_prompts.get(
            dimension,
            f"评估{dimension.value}维度："
        )
        
        context_str = ""
        if context:
            context_str = f"\n上下文信息：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        
        return f"""请对以下文本的【{dimension.value}】维度进行专业评估：

{dimension_desc}
{context_str}

待评估文本：
{text[:5000]}  # 最多取前5000字符

请以 JSON 格式输出评估结果：

```json
{{
  "score": 85,
  "level": "good",
  "strengths": [
    "优点1",
    "优点2"
  ],
  "weaknesses": [
    "不足1",
    "不足2"
  ],
  "suggestions": [
    "改进建议1",
    "改进建议2"
  ],
  "analysis": "详细分析说明（可选）"
}}
```

说明：
- score: 分数 (0-100)
- level: 等级 (excellent/good/satisfactory/needs_improvement/poor)
- strengths: 优点列表（可选）
- weaknesses: 不足列表（可选）
- suggestions: 改进建议（必需）
- analysis: 详细分析（可选）

只输出 JSON，不要有其他说明文字。
"""
    
    def _parse_dimension_result(
        self,
        content: str,
        dimension: QualityDimension
    ) -> DimensionScore:
        """解析维度评估结果"""
        
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            data = json.loads(json_match.group())
            
            # 提取字段
            score = float(data.get("score", 0))
            level_str = data.get("level", "poor")
            
            # 映射等级
            level_map = {
                "excellent": QualityLevel.EXCELLENT,
                "good": QualityLevel.GOOD,
                "satisfactory": QualityLevel.SATISFACTORY,
                "needs_improvement": QualityLevel.NEEDS_IMPROVEMENT,
                "poor": QualityLevel.POOR,
            }
            level = level_map.get(level_str.lower(), QualityLevel.POOR)
            
            return DimensionScore(
                dimension=dimension,
                score=score,
                level=level,
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestions=data.get("suggestions", [])
            )
            
        except Exception as e:
            logger.error(f"Failed to parse dimension result: {e}")
            return DimensionScore(
                dimension=dimension,
                score=0.0,
                level=QualityLevel.POOR,
                weaknesses=[f"解析评估结果失败: {str(e)}"],
                suggestions=["请重新进行评估"]
            )
    
    def _create_error_dimension_score(
        self,
        dimension: QualityDimension,
        error_msg: str
    ) -> DimensionScore:
        """创建错误状态的维度评分"""
        return DimensionScore(
            dimension=dimension,
            score=0.0,
            level=QualityLevel.POOR,
            weaknesses=[f"评估失败: {error_msg}"],
            suggestions=["请检查输入并重试", "如果问题持续，请联系技术支持"]
        )
    
    def _calculate_weighted_average(
        self,
        dimension_scores: List[DimensionScore]
    ) -> float:
        """计算加权平均分"""
        if not dimension_scores:
            return 0.0
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for ds in dimension_scores:
            weight = self.default_weights.get(ds.dimension, 1.0)
            weighted_sum += ds.score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return round(weighted_sum / total_weight, 2)
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """根据分数确定质量等级"""
        for level, threshold in sorted(
            self.score_thresholds.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if score >= threshold:
                return level
        return QualityLevel.POOR
    
    def _generate_evaluation_summary(
        self,
        dimension_scores: List[DimensionScore],
        weighted_average: float
    ) -> str:
        """生成评估摘要"""
        
        # 统计
        total = len(dimension_scores)
        excellent = sum(1 for ds in dimension_scores if ds.level == QualityLevel.EXCELLENT)
        good = sum(1 for ds in dimension_scores if ds.level == QualityLevel.GOOD)
        poor = sum(1 for ds in dimension_scores if ds.level in [QualityLevel.POOR, QualityLevel.NEEDS_IMPROVEMENT])
        
        # 找出最高和最低维度
        sorted_scores = sorted(dimension_scores, key=lambda x: x.score, reverse=True)
        best = sorted_scores[0] if sorted_scores else None
        worst = sorted_scores[-1] if sorted_scores else None
        
        summary = f"""本文质量总体评分为 {weighted_average:.1f}/100。

在 {total} 个评估维度中：
- 优秀 ({QualityLevel.EXCELLENT.value}): {excellent} 个维度
- 良好 ({QualityLevel.GOOD.value}): {good} 个维度
- 待改进或较差: {poor} 个维度
"""
        
        if best:
            summary += f"\n表现最佳维度: {best.dimension.value} ({best.score:.1f}分)\n"
        if worst and worst != best:
            summary += f"需要改进维度: {worst.dimension.value} ({worst.score:.1f}分)\n"
        
        return summary
    
    def _generate_detailed_analysis(
        self,
        dimension_scores: List[DimensionScore]
    ) -> str:
        """生成详细分析"""
        lines = ["# 详细质量分析报告\n"]
        
        for ds in dimension_scores:
            lines.append(f"## {ds.dimension.value.upper()}: {ds.score:.1f}/100 ({ds.level.value})\n")
            
            if ds.strengths:
                lines.append("**优势**:\n")
                for s in ds.strengths:
                    lines.append(f"- {s}\n")
                lines.append("\n")
            
            if ds.weaknesses:
                lines.append("**不足**:\n")
                for w in ds.weaknesses:
                    lines.append(f"- {w}\n")
                lines.append("\n")
            
            if ds.suggestions:
                lines.append("**改进建议**:\n")
                for s in ds.suggestions:
                    lines.append(f"- {s}\n")
                lines.append("\n")
            
            lines.append("---\n\n")
        
        return "".join(lines)
    
    def _extract_priority_improvements(
        self,
        dimension_scores: List[DimensionScore]
    ) -> List[str]:
        """提取优先改进项"""
        
        # 筛选低分维度
        low_scores = [ds for ds in dimension_scores if ds.score < 70]
        
        # 按分数排序（低到高）
        sorted_low = sorted(low_scores, key=lambda x: x.score)
        
        improvements = []
        for ds in sorted_low[:3]:  # 最多取3个
            if ds.suggestions:
                improvements.append(f"【{ds.dimension.value}】(得分{ds.score:.1f}) - 首要建议: {ds.suggestions[0]}")
            else:
                improvements.append(f"【{ds.dimension.value}】(得分{ds.score:.1f}) - 需要整体提升")
        
        return improvements


# 便捷函数

async def evaluate_quality(
    text: str,
    deepseek_client: DeepSeekClient,
    context: Optional[Dict[str, Any]] = None
) -> QualityReport:
    """
    便捷函数：快速评估文本质量
    
    Args:
        text: 待评估文本
        deepseek_client: DeepSeek 客户端
        context: 上下文
        
    Returns:
        质量评估报告
    """
    evaluator = QualityEvaluator(deepseek_client)
    return await evaluator.evaluate(text, context)


async def quick_quality_score(
    text: str,
    deepseek_client: DeepSeekClient
) -> float:
    """
    便捷函数：快速获取质量分数
    
    Args:
        text: 待评估文本
        deepseek_client: DeepSeek 客户端
        
    Returns:
        质量分数 (0-100)
    """
    evaluator = QualityEvaluator(deepseek_client)
    return await evaluator.quick_score(text)
