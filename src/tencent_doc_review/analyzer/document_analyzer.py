"""Main document analyzer orchestration."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from ..llm.base import LLMClient
from ..mcp_client import Comment, TencentDocMCPClient
from .fact_checker import FactCheckResult, FactChecker
from .quality_evaluator import QualityEvaluator, QualityReport
from .structure_matcher import StructureMatchResult, StructureMatcher


class AnalysisType(Enum):
    FULL = "full"
    FACT_CHECK_ONLY = "fact_check"
    STRUCTURE_ONLY = "structure"
    QUALITY_ONLY = "quality"
    CUSTOM = "custom"


@dataclass
class AnalysisConfig:
    analysis_type: AnalysisType = AnalysisType.FULL
    enable_fact_check: bool = True
    enable_structure_match: bool = True
    enable_quality_eval: bool = True
    fact_check_config: Dict[str, Any] = field(default_factory=dict)
    structure_match_config: Dict[str, Any] = field(default_factory=dict)
    quality_eval_config: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 5
    max_concurrency: int = 3
    timeout: int = 300

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisConfig":
        config = cls()
        if "analysis_type" in data:
            config.analysis_type = AnalysisType(data["analysis_type"])
        for key in (
            "enable_fact_check",
            "enable_structure_match",
            "enable_quality_eval",
            "fact_check_config",
            "structure_match_config",
            "quality_eval_config",
            "batch_size",
            "max_concurrency",
            "timeout",
        ):
            if key in data:
                setattr(config, key, data[key])
        return config

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_type": self.analysis_type.value,
            "enable_fact_check": self.enable_fact_check,
            "enable_structure_match": self.enable_structure_match,
            "enable_quality_eval": self.enable_quality_eval,
            "fact_check_config": self.fact_check_config,
            "structure_match_config": self.structure_match_config,
            "quality_eval_config": self.quality_eval_config,
            "batch_size": self.batch_size,
            "max_concurrency": self.max_concurrency,
            "timeout": self.timeout,
        }


@dataclass
class AnalysisResult:
    document_id: str = ""
    document_title: str = ""
    analysis_type: AnalysisType = AnalysisType.FULL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    fact_check_results: List[FactCheckResult] = field(default_factory=list)
    structure_match_result: Optional[StructureMatchResult] = None
    quality_report: Optional[QualityReport] = None
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "analysis_type": self.analysis_type.value,
            "timestamp": self.timestamp,
            "fact_check_results": [item.to_dict() for item in self.fact_check_results],
            "structure_match_result": self.structure_match_result.to_dict() if self.structure_match_result else None,
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Document Review Report",
            "",
            f"- Title: {self.document_title or 'Untitled'}",
            f"- Analysis Type: {self.analysis_type.value}",
            f"- Timestamp: {self.timestamp}",
            "",
            "## Summary",
            "",
            self.summary or "No summary generated.",
            "",
        ]

        if self.structure_match_result:
            lines.extend(
                [
                    "## Structure Match",
                    "",
                    f"- Overall Score: {self.structure_match_result.overall_score:.1%}",
                    "",
                ]
            )
            for match in self.structure_match_result.section_matches:
                lines.append(f"- {match.template_section.title}: {match.status.value}")
            lines.append("")

        if self.quality_report:
            lines.extend(
                [
                    "## Quality Evaluation",
                    "",
                    f"- Overall Score: {self.quality_report.overall_score:.1f}/100",
                    f"- Level: {self.quality_report.overall_level.value}",
                    "",
                ]
            )

        if self.fact_check_results:
            lines.extend(["## Fact Check", ""])
            for item in self.fact_check_results:
                lines.append(
                    f"- {item.original_text or item.claim_content}: {item.verification_status.value} ({item.confidence:.0%})"
                )
            lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for item in self.recommendations:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"


class DocumentAnalyzer:
    """Coordinates fact check, structure match, and quality evaluation."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        mcp_client: Optional[TencentDocMCPClient] = None,
        config: Optional[Dict[str, Any]] = None,
        deepseek_client: Optional[LLMClient] = None,
    ) -> None:
        resolved_llm_client = llm_client or deepseek_client
        if resolved_llm_client is None:
            raise ValueError("An llm_client is required")

        self.llm_client = resolved_llm_client
        self.mcp_client = mcp_client
        self.config = config or {}
        self.fact_checker = FactChecker(
            llm_client=resolved_llm_client,
            search_client=None,
            config=self.config.get("fact_check_config", {}),
        )
        self.structure_matcher = StructureMatcher(
            llm_client=resolved_llm_client,
            config=self.config.get("structure_match_config", {}),
        )
        self.quality_evaluator = QualityEvaluator(
            llm_client=resolved_llm_client,
            config=self.config.get("quality_eval_config", {}),
        )

    async def analyze(
        self,
        document_text: str,
        template_text: Optional[str] = None,
        document_id: str = "",
        document_title: str = "",
        context: Optional[Dict[str, Any]] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> AnalysisResult:
        config = config or AnalysisConfig()
        analysis_context = dict(context or {})
        analysis_context.update(
            {
                "document_id": document_id,
                "document_title": document_title,
                "analysis_type": config.analysis_type.value,
            }
        )

        tasks: List[asyncio.Future] = []
        if config.enable_fact_check:
            tasks.append(asyncio.create_task(self.fact_checker.check(document_text, analysis_context)))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=[])))

        if config.enable_structure_match and template_text:
            tasks.append(
                asyncio.create_task(
                    self.structure_matcher.match(document_text, template_text, analysis_context)
                )
            )
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=None)))

        if config.enable_quality_eval:
            tasks.append(asyncio.create_task(self.quality_evaluator.evaluate(document_text, analysis_context)))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=None)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        fact_check_results = results[0] if not isinstance(results[0], Exception) else []
        structure_match_result = results[1] if not isinstance(results[1], Exception) else None
        quality_report = results[2] if not isinstance(results[2], Exception) else None

        for result in results:
            if isinstance(result, Exception):
                logger.error("Analysis task failed: {}", result)

        summary = self._generate_summary(fact_check_results, structure_match_result, quality_report)
        recommendations = self._generate_recommendations(
            fact_check_results, structure_match_result, quality_report
        )

        return AnalysisResult(
            document_id=document_id,
            document_title=document_title,
            analysis_type=config.analysis_type,
            fact_check_results=fact_check_results or [],
            structure_match_result=structure_match_result,
            quality_report=quality_report,
            summary=summary,
            recommendations=recommendations,
            metadata={
                "document_length": len(document_text),
                "has_template": template_text is not None,
                "analysis_config": config.to_dict(),
            },
        )

    async def analyze_custom(
        self,
        document_text: str,
        checks: List[str],
        template_text: Optional[str] = None,
        **kwargs: Any,
    ) -> AnalysisResult:
        config = AnalysisConfig(
            analysis_type=AnalysisType.CUSTOM,
            enable_fact_check="fact_check" in checks,
            enable_structure_match="structure" in checks and template_text is not None,
            enable_quality_eval="quality" in checks,
        )
        return await self.analyze(
            document_text=document_text,
            template_text=template_text if "structure" in checks else None,
            config=config,
            **kwargs,
        )

    async def analyze_batch(
        self,
        documents: List[Dict[str, Any]],
        config: Optional[AnalysisConfig] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[AnalysisResult]:
        config = config or AnalysisConfig()
        semaphore = asyncio.Semaphore(config.max_concurrency)
        total = len(documents)

        async def run(doc: Dict[str, Any], index: int) -> AnalysisResult:
            async with semaphore:
                if progress_callback:
                    progress_callback(index + 1, total, f"Analyzing: {doc.get('title', 'untitled')}")
                return await self.analyze(
                    document_text=doc.get("text", ""),
                    template_text=doc.get("template"),
                    document_id=doc.get("id", ""),
                    document_title=doc.get("title", ""),
                    context=doc.get("context"),
                    config=config,
                )

        return await asyncio.gather(*(run(doc, index) for index, doc in enumerate(documents)))

    async def analyze_from_tencent_doc(
        self,
        file_id: str,
        template_file_id: Optional[str] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> AnalysisResult:
        if self.mcp_client is None:
            raise ValueError("TencentDoc client is required for Tencent Docs analysis")

        document_text = await self.mcp_client.get_document_content(file_id)
        template_text = None
        if template_file_id:
            template_text = await self.mcp_client.get_document_content(template_file_id)

        result = await self.analyze(
            document_text=document_text,
            template_text=template_text,
            document_id=file_id,
            document_title=file_id,
            config=config,
        )
        await self._add_annotations_to_doc(file_id, result)
        return result

    async def _add_annotations_to_doc(self, file_id: str, result: AnalysisResult) -> None:
        if not self.mcp_client:
            return

        comments: List[Comment] = []
        for issue in result.fact_check_results:
            if issue.verification_status.value in {"incorrect", "disputed", "unverified"}:
                comments.append(
                    Comment(
                        content=f"[fact-check] {issue.suggestion}",
                        position=issue.position,
                        quote_text=issue.original_text,
                        comment_type="warning",
                    )
                )

        if comments:
            await self.mcp_client.add_comments_batch(file_id, comments)

    def save_report(self, result: AnalysisResult, output_path: str, format: str = "markdown") -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format == "markdown":
            path = path.with_suffix(".md")
            content = result.to_markdown()
        elif format == "json":
            path = path.with_suffix(".json")
            content = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        path.write_text(content, encoding="utf-8")
        return str(path)

    def _generate_summary(
        self,
        fact_check_results: List[FactCheckResult],
        structure_match_result: Optional[StructureMatchResult],
        quality_report: Optional[QualityReport],
    ) -> str:
        parts: List[str] = []
        if quality_report:
            parts.append(
                f"Quality score {quality_report.overall_score:.1f}/100 ({quality_report.overall_level.value})."
            )
        if structure_match_result:
            parts.append(f"Structure match {structure_match_result.overall_score:.1%}.")
        if fact_check_results:
            issues = sum(
                1
                for item in fact_check_results
                if item.verification_status.value in {"disputed", "incorrect", "unverified"}
            )
            parts.append(f"Fact check reviewed {len(fact_check_results)} claims, with {issues} flagged.")
        return " ".join(parts) if parts else "No analysis output generated."

    def _generate_recommendations(
        self,
        fact_check_results: List[FactCheckResult],
        structure_match_result: Optional[StructureMatchResult],
        quality_report: Optional[QualityReport],
    ) -> List[str]:
        recommendations: List[str] = []
        if quality_report and quality_report.priority_improvements:
            recommendations.extend(quality_report.priority_improvements[:3])
        if structure_match_result:
            missing = [match for match in structure_match_result.section_matches if match.status.value == "missing"]
            if missing:
                recommendations.append(f"Add {len(missing)} missing sections from the template.")
        if fact_check_results:
            flagged = [
                item
                for item in fact_check_results
                if item.verification_status.value in {"incorrect", "disputed", "unverified"}
            ]
            if flagged:
                recommendations.append(f"Review {len(flagged)} flagged fact-check items.")
        return recommendations[:5]


async def analyze_document(
    document_text: str,
    llm_client: LLMClient,
    template_text: Optional[str] = None,
    mcp_client: Optional[TencentDocMCPClient] = None,
    **kwargs: Any,
) -> AnalysisResult:
    analyzer = DocumentAnalyzer(llm_client=llm_client, mcp_client=mcp_client)
    return await analyzer.analyze(
        document_text=document_text,
        template_text=template_text,
        **kwargs,
    )
