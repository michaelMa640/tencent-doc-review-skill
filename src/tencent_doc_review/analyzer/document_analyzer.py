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

from ..config import get_settings
from ..domain import ReviewIssue, ReviewIssueType, ReviewReport, aggregate_review_issues, build_review_report
from ..llm.base import LLMClient
from ..mcp_client import Comment, TencentDocMCPClient
from .consistency_reviewer import ConsistencyReviewer
from .fact_checker import FactCheckResult, FactChecker, NativeSearchClient, RoutedSearchClient, SearchClient
from .language_reviewer import LanguageReviewer
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
    language_review_config: Dict[str, Any] = field(default_factory=dict)
    consistency_review_config: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 5
    max_concurrency: int = 3
    timeout: int = 300

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisConfig":
        config = cls()
        for key, value in data.items():
            if key == "analysis_type":
                config.analysis_type = AnalysisType(value)
            elif hasattr(config, key):
                setattr(config, key, value)
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
            "language_review_config": self.language_review_config,
            "consistency_review_config": self.consistency_review_config,
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
    language_issues: List[ReviewIssue] = field(default_factory=list)
    consistency_issues: List[ReviewIssue] = field(default_factory=list)
    review_issues: List[ReviewIssue] = field(default_factory=list)
    review_report: Optional[ReviewReport] = None
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
            "language_issues": [item.to_dict() for item in self.language_issues],
            "consistency_issues": [item.to_dict() for item in self.consistency_issues],
            "review_issues": [item.to_dict() for item in self.review_issues],
            "review_report": self.review_report.to_dict() if self.review_report else None,
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
            lines.extend(self._render_structure_match_table(self.structure_match_result))
            lines.append("")
            for match in self.structure_match_result.section_matches:
                lines.append(f"- {match.template_section.title}: {match.status.value}")
            lines.append("")
        structure_issues = [item for item in self.review_issues if item.issue_type == ReviewIssueType.STRUCTURE]
        if structure_issues:
            lines.extend(["## Structure Issues", ""])
            for item in structure_issues:
                lines.append(f"- [{item.severity.value}] {item.title}: {item.description}")
                if item.suggestion:
                    lines.append(f"  Suggestion: {item.suggestion}")
            lines.append("")
        if self.fact_check_results:
            lines.extend(["## Fact Check", ""])
            for item in self.fact_check_results:
                lines.append(f"- {item.original_text or item.claim_content}: {item.verification_status.value} ({item.confidence:.0%})")
                if item.search_trace.get("performed"):
                    lines.append(
                        "  Search Trace: "
                        f"{item.search_trace.get('provider', 'unknown')} "
                        f"raw={item.search_trace.get('raw_count', 0)} "
                        f"filtered={item.search_trace.get('filtered_count', 0)}"
                    )
                formatted_sources = self._format_sources_for_markdown(item.sources)
                if formatted_sources:
                    lines.append(f"  Sources: {formatted_sources}")
            lines.append("")
        if self.language_issues:
            lines.extend(["## Language Issues", ""])
            for item in self.language_issues:
                lines.append(f"- [{item.severity.value}] {item.title}: {item.source_excerpt or item.description}")
            lines.append("")
        if self.consistency_issues:
            lines.extend(["## Consistency Issues", ""])
            for item in self.consistency_issues:
                lines.append(f"- [{item.severity.value}] {item.title}: {item.description}")
            lines.append("")
        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            lines.extend(f"- {item}" for item in self.recommendations)
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _format_sources_for_markdown(self, sources: List[Dict[str, str]]) -> str:
        parts: List[str] = []
        for item in sources:
            title = str(item.get("title") or "来源").strip()
            url = str(item.get("url") or "").strip()
            if url:
                parts.append(f"[{title}]({url})")
            elif title:
                parts.append(title)
        return "; ".join(parts)

    def _render_structure_match_table(self, structure_match_result: StructureMatchResult) -> List[str]:
        lines = [
            "| 模板章节 | 当前文章是否已有 | 当前命中章节名 | 状态说明 |",
            "| --- | --- | --- | --- |",
        ]
        for match in structure_match_result.section_matches:
            status = match.status.value
            status_label = {
                "matched": "已覆盖",
                "missing": "缺失",
                "partial": "部分匹配",
                "misplaced": "位置不对应",
                "extra": "额外章节",
            }.get(status, status)
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(match.template_section.title or "").strip(),
                        "✓" if status == "matched" else "✗",
                        str(match.document_section.title if match.document_section else "").strip(),
                        status_label,
                    ]
                )
                + " |"
            )
        return lines


class DocumentAnalyzer:
    """Coordinates fact check, structure match, language review, consistency review and quality evaluation."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        mcp_client: Optional[TencentDocMCPClient] = None,
        search_client: Optional[SearchClient] = None,
        config: Optional[Dict[str, Any]] = None,
        deepseek_client: Optional[LLMClient] = None,
    ) -> None:
        resolved_llm_client = llm_client or deepseek_client
        if resolved_llm_client is None:
            raise ValueError("An llm_client is required")

        self.llm_client = resolved_llm_client
        self.mcp_client = mcp_client
        self.config = config or {}
        self.search_client = search_client or self._build_search_client(self.config.get("fact_check_config", {}))
        self.fact_checker = FactChecker(
            llm_client=resolved_llm_client,
            search_client=self.search_client,
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
        self.language_reviewer = LanguageReviewer(
            llm_client=resolved_llm_client,
            config=self.config.get("language_review_config", {}),
        )
        self.consistency_reviewer = ConsistencyReviewer(
            llm_client=resolved_llm_client,
            config=self.config.get("consistency_review_config", {}),
        )

    def _build_search_client(self, fact_check_config: Dict[str, Any]) -> SearchClient:
        settings = get_settings()
        fact_check_mode = str(fact_check_config.get("fact_check_mode") or settings.fact_check_mode or "auto").strip().lower()
        provider = fact_check_config.get("search_provider") or settings.search_provider
        api_client = SearchClient(
            api_key=fact_check_config.get("search_api_key") or settings.search_api_key,
            provider=provider,
            base_url=fact_check_config.get("search_base_url") or settings.search_base_url,
            timeout=int(fact_check_config.get("search_timeout_seconds") or settings.search_timeout),
            max_results=int(fact_check_config.get("search_max_results") or settings.search_max_results),
            search_depth=str(fact_check_config.get("search_depth") or settings.search_depth),
            topic=str(fact_check_config.get("search_topic") or settings.search_topic),
        )
        native_client = NativeSearchClient(llm_client=self.llm_client)
        if fact_check_mode == "offline":
            return RoutedSearchClient(mode="offline", native_client=native_client, api_client=api_client)
        if fact_check_mode == "api":
            return RoutedSearchClient(mode="api", native_client=native_client, api_client=api_client)
        if fact_check_mode in {"native", "agent"}:
            return RoutedSearchClient(mode="native", native_client=native_client, api_client=api_client)
        return RoutedSearchClient(mode=fact_check_mode, native_client=native_client, api_client=api_client)

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

        tasks: List[asyncio.Task[Any]] = [
            asyncio.create_task(self.fact_checker.check(document_text, analysis_context))
            if config.enable_fact_check
            else asyncio.create_task(asyncio.sleep(0, result=[])),
            asyncio.create_task(self.structure_matcher.match(document_text, template_text, analysis_context))
            if config.enable_structure_match and template_text
            else asyncio.create_task(asyncio.sleep(0, result=None)),
            asyncio.create_task(self.quality_evaluator.evaluate(document_text, analysis_context))
            if config.enable_quality_eval
            else asyncio.create_task(asyncio.sleep(0, result=None)),
            asyncio.create_task(self.language_reviewer.review(document_text, analysis_context))
            if config.enable_quality_eval
            else asyncio.create_task(asyncio.sleep(0, result=[])),
            asyncio.create_task(self.consistency_reviewer.review(document_text, analysis_context))
            if config.enable_quality_eval
            else asyncio.create_task(asyncio.sleep(0, result=[])),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        fact_check_results = results[0] if not isinstance(results[0], Exception) else []
        structure_match_result = results[1] if not isinstance(results[1], Exception) else None
        quality_report = results[2] if not isinstance(results[2], Exception) else None
        language_issues = results[3] if not isinstance(results[3], Exception) else []
        consistency_issues = results[4] if not isinstance(results[4], Exception) else []

        for result in results:
            if isinstance(result, Exception):
                logger.error("Analysis task failed: {}", result)

        summary = self._generate_summary(
            fact_check_results or [],
            structure_match_result,
            quality_report,
            consistency_issues or [],
        )
        recommendations = self._generate_recommendations(
            fact_check_results or [],
            structure_match_result,
            quality_report,
            consistency_issues or [],
        )
        review_issues = aggregate_review_issues(
            fact_check_results or [],
            structure_match_result,
            quality_report,
            language_issues=language_issues or [],
            consistency_issues=consistency_issues or [],
        )
        metadata = {
            "document_length": len(document_text),
            "has_template": template_text is not None,
            "analysis_config": config.to_dict(),
            "fact_check_mode": config.fact_check_config.get("fact_check_mode") or get_settings().fact_check_mode,
        }
        review_report = build_review_report(
            summary=summary,
            recommendations=recommendations,
            issues=review_issues,
            fact_check_results=fact_check_results or [],
            structure_match_result=structure_match_result,
            quality_report=quality_report,
            metadata=metadata,
        )
        return AnalysisResult(
            document_id=document_id,
            document_title=document_title,
            analysis_type=config.analysis_type,
            fact_check_results=fact_check_results or [],
            structure_match_result=structure_match_result,
            quality_report=quality_report,
            language_issues=language_issues or [],
            consistency_issues=consistency_issues or [],
            review_issues=review_issues,
            review_report=review_report,
            summary=summary,
            recommendations=recommendations,
            metadata=metadata,
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
        template_text: Optional[str] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> AnalysisResult:
        if self.mcp_client is None:
            raise ValueError("TencentDoc client is required for Tencent Docs analysis")
        document_info, document_text = await self.mcp_client.get_document_bundle(file_id)
        resolved_template_text = template_text
        if template_file_id:
            resolved_template_text = await self.mcp_client.get_document_content(template_file_id)
        result = await self.analyze(
            document_text=document_text,
            template_text=resolved_template_text,
            document_id=file_id,
            document_title=document_info.title or file_id,
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
        consistency_issues: List[ReviewIssue],
    ) -> str:
        parts: List[str] = []
        if quality_report:
            parts.append(f"Quality score {quality_report.overall_score:.1f}/100 ({quality_report.overall_level.value}).")
        if structure_match_result:
            parts.append(f"Structure match {structure_match_result.overall_score:.1%}.")
        if fact_check_results:
            issues = sum(
                1
                for item in fact_check_results
                if item.verification_status.value in {"disputed", "incorrect", "unverified", "partial"}
            )
            parts.append(f"Fact check reviewed {len(fact_check_results)} claims, with {issues} flagged.")
            search_count = sum(1 for item in fact_check_results if item.search_trace.get("performed"))
            actual_modes: dict[str, int] = {}
            fallback_count = 0
            reasons: List[str] = []
            for item in fact_check_results:
                trace = item.search_trace if isinstance(item.search_trace, dict) else {}
                if trace.get("performed"):
                    actual_mode = str(trace.get("actual_mode") or "").strip().lower()
                    provider = str(trace.get("provider") or "").strip().lower()
                    label = ""
                    if actual_mode == "native" or provider == "openai":
                        label = "native web search"
                    elif actual_mode == "api" or provider == "tavily":
                        label = "Tavily API"
                    if label:
                        actual_modes[label] = actual_modes.get(label, 0) + 1
                if trace.get("fallback_triggered"):
                    fallback_count += 1
                reason = str(trace.get("reason") or trace.get("error") or "").strip()
                if reason:
                    reasons.append(reason)
            if search_count > 0 and actual_modes:
                execution_summary = ", ".join(f"{label}={count}" for label, count in actual_modes.items())
                parts.append(f"Network search executed for {search_count} claims via {execution_summary}.")
            if fallback_count > 0:
                parts.append(f"Fallback triggered for {fallback_count} claims.")
            if search_count == 0 and reasons:
                parts.append(f"Network search executed for 0 claims. Reason: {reasons[0]}")
        if consistency_issues:
            parts.append(f"Found {len(consistency_issues)} potential consistency issues.")
        return " ".join(parts) if parts else "No analysis output generated."

    def _generate_recommendations(
        self,
        fact_check_results: List[FactCheckResult],
        structure_match_result: Optional[StructureMatchResult],
        quality_report: Optional[QualityReport],
        consistency_issues: List[ReviewIssue],
    ) -> List[str]:
        recommendations: List[str] = []
        if quality_report and quality_report.priority_improvements:
            recommendations.extend(
                item for item in quality_report.priority_improvements[:3] if "格式" not in item and "format" not in item.lower()
            )
        if fact_check_results:
            flagged = [
                item
                for item in fact_check_results
                if item.verification_status.value in {"incorrect", "disputed", "unverified", "partial"}
            ]
            if flagged:
                recommendations.append(f"请优先复查 {len(flagged)} 处事实性表述。")
        if consistency_issues:
            recommendations.append(f"请复核 {len(consistency_issues)} 处前后表述是否一致。")
        if structure_match_result:
            missing = [match for match in structure_match_result.section_matches if match.status.value == "missing"]
            if missing:
                missing_titles = [match.template_section.title for match in missing if match.template_section.title]
                if missing_titles:
                    recommendations.append(f"请补齐这些缺失章节：{'、'.join(missing_titles)}。")
        return recommendations[:5]


async def analyze_document(
    document_text: str,
    llm_client: Optional[LLMClient] = None,
    template_text: Optional[str] = None,
    mcp_client: Optional[TencentDocMCPClient] = None,
    deepseek_client: Optional[LLMClient] = None,
    **kwargs: Any,
) -> AnalysisResult:
    analyzer = DocumentAnalyzer(llm_client=llm_client, deepseek_client=deepseek_client, mcp_client=mcp_client)
    return await analyzer.analyze(document_text=document_text, template_text=template_text, **kwargs)
