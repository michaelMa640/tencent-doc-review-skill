"""Quality evaluation for article review workflows."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from ..llm.base import LLMClient
from ..llm.structured_output import extract_json_payload


class QualityDimension(Enum):
    """Dimensions used in article quality evaluation."""

    COMPLETENESS = "content_completeness"
    CLARITY = "logical_clarity"
    ARGUMENTATION = "argumentation_quality"
    DATA_ACCURACY = "data_accuracy"
    LANGUAGE = "language_expression"
    FORMAT = "format_compliance"
    OVERALL = "overall"


EvaluationDimension = QualityDimension
EvaluationDimension.CONTENT_COMPLETENESS = QualityDimension.COMPLETENESS
EvaluationDimension.LOGICAL_CLARITY = QualityDimension.CLARITY
EvaluationDimension.ARGUMENTATION_QUALITY = QualityDimension.ARGUMENTATION
EvaluationDimension.LANGUAGE_EXPRESSION = QualityDimension.LANGUAGE
EvaluationDimension.FORMAT_COMPLIANCE = QualityDimension.FORMAT


class QualityLevel(Enum):
    """Overall quality buckets."""

    EXCELLENT = "excellent"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


QualityLevel.ACCEPTABLE = QualityLevel.SATISFACTORY
QualityLevel.CRITICAL = QualityLevel.POOR


@dataclass
class DimensionScore:
    dimension: QualityDimension
    score: float = 0.0
    weight: float = 1.0
    level: QualityLevel = QualityLevel.POOR
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level.value,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
        }


@dataclass
class QualityReport:
    overall_score: float = 0.0
    overall_level: QualityLevel = QualityLevel.POOR
    dimension_scores: List[DimensionScore] = field(default_factory=list)
    weighted_average: float = 0.0
    summary: str = ""
    detailed_analysis: str = ""
    priority_improvements: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def strengths(self) -> List[str]:
        items: List[str] = []
        for score in self.dimension_scores:
            items.extend(score.strengths)
        return items

    @property
    def weaknesses(self) -> List[str]:
        items: List[str] = []
        for score in self.dimension_scores:
            items.extend(score.weaknesses)
        return items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "overall_level": self.overall_level.value,
            "dimension_scores": [score.to_dict() for score in self.dimension_scores],
            "weighted_average": round(self.weighted_average, 2),
            "summary": self.summary,
            "detailed_analysis": self.detailed_analysis,
            "priority_improvements": self.priority_improvements,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        lines = [
            "# 质量评估报告",
            "",
            f"**评估时间**: {self.created_at}",
            f"**总体评分**: {self.overall_score:.1f}/100",
            f"**质量等级**: {self.overall_level.value}",
            "",
            "## 评分概览",
            "",
            "| 维度 | 得分 | 等级 | 权重 |",
            "|------|------|------|------|",
        ]
        for score in self.dimension_scores:
            lines.append(
                f"| {score.dimension.value} | {score.score:.1f} | {score.level.value} | {score.weight:.2f} |"
            )
        lines.extend(
            [
                "",
                "## 评估摘要",
                "",
                self.summary or "暂无摘要。",
                "",
                "## 优先改进项",
                "",
            ]
        )
        if self.priority_improvements:
            lines.extend(f"{index}. {item}" for index, item in enumerate(self.priority_improvements, start=1))
        else:
            lines.append("当前无明显需优先处理的问题。")
        return "\n".join(lines).strip() + "\n"


class QualityEvaluator:
    """Run multi-dimension quality evaluation against a document."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        config: Optional[Dict[str, Any]] = None,
        deepseek_client: Optional[LLMClient] = None,
    ) -> None:
        self.llm = llm_client or deepseek_client
        if self.llm is None:
            raise ValueError("An llm_client is required")
        self.config = config or {}
        self.default_weights = self.config.get(
            "default_weights",
            {
                QualityDimension.COMPLETENESS: 0.20,
                QualityDimension.CLARITY: 0.15,
                QualityDimension.ARGUMENTATION: 0.15,
                QualityDimension.DATA_ACCURACY: 0.15,
                QualityDimension.LANGUAGE: 0.15,
                QualityDimension.FORMAT: 0.10,
            },
        )
        self.score_thresholds = self.config.get(
            "score_thresholds",
            {
                QualityLevel.EXCELLENT: 90,
                QualityLevel.GOOD: 80,
                QualityLevel.SATISFACTORY: 70,
                QualityLevel.NEEDS_IMPROVEMENT: 60,
                QualityLevel.POOR: 0,
            },
        )
        self.provider_name = self._detect_provider_name()
        self.use_combined_call = bool(self.config.get("use_combined_call", self.provider_name == "minimax"))
        default_timeout = 120 if self.provider_name == "minimax" else 45
        self.timeout_seconds = float(self.config.get("timeout_seconds", default_timeout))
        self.max_retries = int(self.config.get("max_retries", 2))
        self.retry_delay_seconds = float(self.config.get("retry_delay_seconds", 1))
        self.temperature = float(self.config.get("temperature", 0.1))
        logger.info("QualityEvaluator initialized")

    async def evaluate(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        dimensions: Optional[List[QualityDimension]] = None,
    ) -> QualityReport:
        logger.info("Starting quality evaluation ({} chars)", len(text))

        selected_dimensions = dimensions or [
            QualityDimension.COMPLETENESS,
            QualityDimension.CLARITY,
            QualityDimension.ARGUMENTATION,
            QualityDimension.DATA_ACCURACY,
            QualityDimension.LANGUAGE,
            QualityDimension.FORMAT,
        ]

        if not text.strip():
            empty_scores = [
                DimensionScore(
                    dimension=dimension,
                    score=0.0,
                    level=QualityLevel.POOR,
                    weaknesses=["Document is empty"],
                    suggestions=["Provide document content before evaluation."],
                )
                for dimension in selected_dimensions
            ]
            return QualityReport(
                overall_score=0.0,
                overall_level=QualityLevel.POOR,
                dimension_scores=empty_scores,
                weighted_average=0.0,
                summary="Document is empty and cannot be meaningfully evaluated.",
                detailed_analysis="No content provided.",
                priority_improvements=["Provide document content before evaluation."],
                metadata={
                    "text_length": 0,
                    "evaluated_dimensions": [dimension.value for dimension in selected_dimensions],
                    "evaluation_version": "2.0",
                },
            )

        report = await self._evaluate_dimensions(text, context, selected_dimensions)
        logger.info("Quality evaluation completed: {:.1f}/100 ({})", report.overall_score, report.overall_level.value)
        return report

    async def evaluate_dimension(
        self,
        text: str,
        dimension: QualityDimension,
        context: Optional[Dict[str, Any]] = None,
    ) -> DimensionScore:
        stripped = text.strip()
        if stripped and len(stripped) < 50 and dimension == QualityDimension.COMPLETENESS:
            return DimensionScore(
                dimension=dimension,
                score=40.0,
                level=QualityLevel.POOR,
                weaknesses=["Content is too short to be complete."],
                suggestions=["Expand the document with essential sections and supporting details."],
            )

        prompt = self._build_dimension_prompt(text, dimension, context)
        try:
            analysis = await self._analyze_with_retry(prompt, analysis_type="quality")
            content = analysis.content if hasattr(analysis, "content") else str(analysis)
        except Exception as exc:
            logger.error("LLM evaluation failed for dimension {}: {}", dimension.value, exc)
            return self._create_error_dimension_score(dimension, str(exc))

        return self._parse_dimension_result(content, dimension)

    async def _evaluate_dimensions(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
        selected_dimensions: List[QualityDimension],
    ) -> QualityReport:
        if self.use_combined_call:
            try:
                return await self._evaluate_all_dimensions(text, context, selected_dimensions)
            except Exception as exc:
                logger.warning("Combined quality evaluation failed, falling back to per-dimension mode: {}", exc)

        dimension_scores: List[DimensionScore] = []
        for dimension in selected_dimensions:
            try:
                score = await self.evaluate_dimension(text, dimension, context)
                dimension_scores.append(score)
                logger.debug("Dimension {}: {:.1f}", dimension.value, score.score)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error("Failed to evaluate dimension {}: {}", dimension.value, exc)
                dimension_scores.append(
                    DimensionScore(
                        dimension=dimension,
                        score=0.0,
                        level=QualityLevel.POOR,
                        weaknesses=[f"评估失败: {exc}"],
                        suggestions=["请检查输入并重试。"],
                    )
                )

        return self._build_report_from_dimension_scores(text, selected_dimensions, dimension_scores)

    async def _evaluate_all_dimensions(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
        selected_dimensions: List[QualityDimension],
    ) -> QualityReport:
        prompt = self._build_combined_prompt(text, context, selected_dimensions)
        analysis = await self._analyze_with_retry(
            prompt,
            analysis_type="quality",
            max_tokens=4096,
        )
        content = analysis.content if hasattr(analysis, "content") else str(analysis)
        payload = extract_json_payload(content)
        if not isinstance(payload, dict):
            raise ValueError("Combined quality response is not a JSON object")

        dimension_scores = self._parse_combined_dimension_scores(payload, selected_dimensions)
        if not dimension_scores:
            raise ValueError("Combined quality response did not contain dimension scores")

        report = self._build_report_from_dimension_scores(text, selected_dimensions, dimension_scores)
        if payload.get("summary"):
            report.summary = str(payload.get("summary")).strip()
        if payload.get("priority_improvements"):
            report.priority_improvements = self._normalize_string_list(payload.get("priority_improvements"))
        overall_score = payload.get("overall_score")
        overall_level = payload.get("overall_level")
        if overall_score is not None:
            report.overall_score = min(100.0, max(0.0, float(overall_score)))
            report.weighted_average = report.overall_score
        if overall_level is not None:
            report.overall_level = self._parse_quality_level(overall_level)
        report.metadata["combined_quality_call"] = True
        return report

    async def quick_score(self, text: str) -> float:
        prompt = (
            "You are giving a fast quality score for a Chinese product research report. "
            "Reply with only one integer between 0 and 100.\n\n"
            f"Text:\n{text[:2000]}"
        )
        try:
            analysis = await self._analyze_with_retry(prompt, analysis_type="quality")
            content = analysis.content if hasattr(analysis, "content") else str(analysis)
            numbers = re.findall(r"\d+", content)
            if numbers:
                score = int(numbers[0])
                return float(min(100, max(0, score)))
            return 50.0
        except Exception as exc:
            logger.error("Quick score failed: {}", exc)
            return 0.0

    async def _analyze_with_retry(self, prompt: str, analysis_type: str, max_tokens: int = 2048) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.llm.analyze(
                        prompt,
                        analysis_type=analysis_type,
                        temperature=self.temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_delay_seconds)
        assert last_error is not None
        raise last_error

    def _build_dimension_prompt(
        self,
        text: str,
        dimension: QualityDimension,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        dimension_prompts = {
            QualityDimension.COMPLETENESS: "Check whether the report covers the required sections and whether each section has enough substance.",
            QualityDimension.CLARITY: "Check whether the report is logically organized and easy to follow.",
            QualityDimension.ARGUMENTATION: "Check whether conclusions are supported by evidence, comparisons, or reasoning.",
            QualityDimension.DATA_ACCURACY: "Check whether data and factual expressions appear cautious, precise, and internally consistent.",
            QualityDimension.LANGUAGE: "Check whether the wording is professional, clear, and concise.",
            QualityDimension.FORMAT: "Check whether there are major structure or readability issues. Ignore minor formatting imperfections.",
        }
        return (
            f"You are asked to evaluate the dimension `{dimension.value}` for a Chinese product research report.\n"
            f"{dimension_prompts.get(dimension, 'Evaluate this dimension professionally.')}\n"
            "Return exactly one JSON object and nothing else. Do not use markdown code fences.\n"
            'Schema: {"score":85,"level":"excellent|good|satisfactory|needs_improvement|poor","strengths":["中文优点"],"weaknesses":["中文问题"],"suggestions":["中文建议"],"analysis":"中文补充说明"}\n'
            "Always return valid JSON even when the text is weak.\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=False)}\n\nText:\n{text[:5000]}"
        )

    def _build_combined_prompt(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
        dimensions: List[QualityDimension],
    ) -> str:
        dimension_list = ", ".join(dimension.value for dimension in dimensions)
        return (
            "You are evaluating a Chinese product research report across multiple quality dimensions.\n"
            "Return exactly one JSON object and nothing else. Do not use markdown code fences.\n"
            f"Evaluate these dimensions: {dimension_list}.\n"
            'Schema: {"overall_score":82,"overall_level":"excellent|good|satisfactory|needs_improvement|poor","summary":"中文摘要","priority_improvements":["中文建议"],"dimension_scores":[{"dimension":"content_completeness","score":80,"level":"good","strengths":["中文优点"],"weaknesses":["中文问题"],"suggestions":["中文建议"]}]}\n'
            "Each requested dimension must appear exactly once in dimension_scores.\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=False)}\n\nText:\n{text[:7000]}"
        )

    def _parse_dimension_result(self, content: str, dimension: QualityDimension) -> DimensionScore:
        try:
            data = extract_json_payload(content)
            if not isinstance(data, dict):
                raise ValueError("Response is not a JSON object")

            score = float(data.get("score", 0))
            score = min(100.0, max(0.0, score))
            level = self._parse_quality_level(data.get("level"))
            strengths = self._normalize_string_list(data.get("strengths"))
            weaknesses = self._normalize_string_list(data.get("weaknesses") or data.get("issues"))
            suggestions = self._normalize_string_list(data.get("suggestions"))
            if not suggestions:
                suggestions = ["建议补充更具体的分析和证据。"]

            return DimensionScore(
                dimension=dimension,
                score=score,
                weight=float(self.default_weights.get(dimension, 1.0)),
                level=level,
                strengths=strengths,
                weaknesses=weaknesses,
                suggestions=suggestions,
            )
        except Exception as exc:
            logger.error("Failed to parse dimension result: {}", exc)
            return DimensionScore(
                dimension=dimension,
                score=0.0,
                weight=float(self.default_weights.get(dimension, 1.0)),
                level=QualityLevel.POOR,
                weaknesses=[f"解析评估结果失败: {exc}"],
                suggestions=["请重新进行评估。"],
            )

    def _create_error_dimension_score(self, dimension: QualityDimension, error_msg: str) -> DimensionScore:
        return DimensionScore(
            dimension=dimension,
            score=0.0,
            weight=float(self.default_weights.get(dimension, 1.0)),
            level=QualityLevel.POOR,
            weaknesses=[f"评估失败: {error_msg}"],
            suggestions=["请检查输入并重试。", "如果问题持续，请调整模型或超时配置。"],
        )

    def _build_report_from_dimension_scores(
        self,
        text: str,
        selected_dimensions: List[QualityDimension],
        dimension_scores: List[DimensionScore],
    ) -> QualityReport:
        weighted_average = self._calculate_weighted_average(dimension_scores)
        overall_level = self._determine_quality_level(weighted_average)
        summary = self._generate_evaluation_summary(dimension_scores, weighted_average)
        detailed_analysis = self._generate_detailed_analysis(dimension_scores)
        priority_improvements = self._extract_priority_improvements(dimension_scores)
        return QualityReport(
            overall_score=weighted_average,
            overall_level=overall_level,
            dimension_scores=dimension_scores,
            weighted_average=weighted_average,
            summary=summary,
            detailed_analysis=detailed_analysis,
            priority_improvements=priority_improvements,
            metadata={
                "text_length": len(text),
                "evaluated_dimensions": [dimension.value for dimension in selected_dimensions],
                "evaluation_version": "2.0",
                "combined_quality_call": False,
            },
        )

    def _parse_combined_dimension_scores(
        self,
        payload: Dict[str, Any],
        selected_dimensions: List[QualityDimension],
    ) -> List[DimensionScore]:
        items = payload.get("dimension_scores")
        if not isinstance(items, list):
            return []

        parsed: Dict[str, DimensionScore] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                dimension = self._parse_dimension_name(item.get("dimension"))
            except ValueError:
                continue
            parsed[dimension.value] = DimensionScore(
                dimension=dimension,
                score=min(100.0, max(0.0, float(item.get("score", 0)))),
                weight=float(self.default_weights.get(dimension, 1.0)),
                level=self._parse_quality_level(item.get("level")),
                strengths=self._normalize_string_list(item.get("strengths")),
                weaknesses=self._normalize_string_list(item.get("weaknesses") or item.get("issues")),
                suggestions=self._normalize_string_list(item.get("suggestions")) or ["建议补充更具体的分析和证据。"],
            )

        dimension_scores: List[DimensionScore] = []
        for dimension in selected_dimensions:
            dimension_scores.append(
                parsed.get(
                    dimension.value,
                    DimensionScore(
                        dimension=dimension,
                        score=0.0,
                        weight=float(self.default_weights.get(dimension, 1.0)),
                        level=QualityLevel.POOR,
                        weaknesses=["该维度未返回有效结果。"],
                        suggestions=["请重新评估该维度。"],
                    ),
                )
            )
        return dimension_scores

    def _calculate_weighted_average(self, dimension_scores: List[DimensionScore]) -> float:
        if not dimension_scores:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        for score in dimension_scores:
            weight = float(self.default_weights.get(score.dimension, score.weight or 1.0))
            weighted_sum += score.score * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 2)

    def _determine_quality_level(self, score: float) -> QualityLevel:
        for level, threshold in sorted(self.score_thresholds.items(), key=lambda item: item[1], reverse=True):
            if score >= threshold:
                return level
        return QualityLevel.POOR

    def _parse_quality_level(self, value: Any) -> QualityLevel:
        normalized = str(value or "poor").strip().lower()
        mapping = {
            "excellent": QualityLevel.EXCELLENT,
            "good": QualityLevel.GOOD,
            "satisfactory": QualityLevel.SATISFACTORY,
            "acceptable": QualityLevel.SATISFACTORY,
            "needs_improvement": QualityLevel.NEEDS_IMPROVEMENT,
            "poor": QualityLevel.POOR,
            "critical": QualityLevel.POOR,
        }
        return mapping.get(normalized, QualityLevel.POOR)

    def _parse_dimension_name(self, value: Any) -> QualityDimension:
        normalized = str(value or "").strip().lower()
        for dimension in QualityDimension:
            if dimension.value == normalized:
                return dimension
        raise ValueError(f"Unknown quality dimension: {value}")

    def _detect_provider_name(self) -> str:
        class_name = self.llm.__class__.__name__.lower()
        model_name = str(getattr(self.llm, "model", "")).lower()
        if "minimax" in class_name or "minimax" in model_name:
            return "minimax"
        if "deepseek" in class_name or "deepseek" in model_name:
            return "deepseek"
        if "openai" in class_name or "gpt" in model_name:
            return "openai"
        return class_name

    def _generate_evaluation_summary(
        self,
        dimension_scores: List[DimensionScore],
        weighted_average: float,
    ) -> str:
        total = len(dimension_scores)
        excellent = sum(1 for score in dimension_scores if score.level == QualityLevel.EXCELLENT)
        good = sum(1 for score in dimension_scores if score.level == QualityLevel.GOOD)
        weaker = sum(
            1
            for score in dimension_scores
            if score.level in {QualityLevel.NEEDS_IMPROVEMENT, QualityLevel.POOR}
        )
        sorted_scores = sorted(dimension_scores, key=lambda item: item.score, reverse=True)
        best = sorted_scores[0] if sorted_scores else None
        worst = sorted_scores[-1] if sorted_scores else None

        parts = [
            f"本文整体质量评分为 {weighted_average:.1f}/100。",
            f"在 {total} 个维度中，优秀 {excellent} 项，良好 {good} 项，待改进或较弱 {weaker} 项。",
        ]
        if best:
            parts.append(f"表现最好的是 {best.dimension.value}（{best.score:.1f} 分）。")
        if worst and worst is not best:
            parts.append(f"最需要补强的是 {worst.dimension.value}（{worst.score:.1f} 分）。")
        return " ".join(parts)

    def _generate_detailed_analysis(self, dimension_scores: List[DimensionScore]) -> str:
        lines = ["# 详细质量分析报告", ""]
        for score in dimension_scores:
            lines.append(f"## {score.dimension.value}: {score.score:.1f}/100 ({score.level.value})")
            if score.strengths:
                lines.append("**优势**")
                lines.extend(f"- {item}" for item in score.strengths)
            if score.weaknesses:
                lines.append("**问题**")
                lines.extend(f"- {item}" for item in score.weaknesses)
            if score.suggestions:
                lines.append("**建议**")
                lines.extend(f"- {item}" for item in score.suggestions)
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _extract_priority_improvements(self, dimension_scores: List[DimensionScore]) -> List[str]:
        low_scores = sorted(
            [score for score in dimension_scores if score.score < 70],
            key=lambda item: item.score,
        )
        improvements: List[str] = []
        for score in low_scores[:3]:
            first_suggestion = score.suggestions[0] if score.suggestions else "需要进一步完善。"
            improvements.append(f"【{score.dimension.value}，得分 {score.score:.1f}】优先建议：{first_suggestion}")
        return improvements

    def _normalize_string_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        return []


async def evaluate_quality(
    text: str,
    llm_client: LLMClient,
    context: Optional[Dict[str, Any]] = None,
) -> QualityReport:
    evaluator = QualityEvaluator(llm_client=llm_client)
    return await evaluator.evaluate(text, context)


async def quick_quality_score(
    text: str,
    llm_client: LLMClient,
) -> float:
    evaluator = QualityEvaluator(llm_client=llm_client)
    return await evaluator.quick_score(text)
