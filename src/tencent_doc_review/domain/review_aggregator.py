"""Helpers for aggregating analyzer outputs into unified review models."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..analyzer.fact_checker import FactCheckResult
from ..analyzer.quality_evaluator import QualityLevel, QualityReport
from ..analyzer.structure_matcher import StructureMatchResult
from .review_models import ReviewIssue, ReviewIssueType, ReviewReport, ReviewSeverity


def aggregate_review_issues(
    fact_check_results: List[FactCheckResult],
    structure_match_result: Optional[StructureMatchResult],
    quality_report: Optional[QualityReport],
    language_issues: Optional[List[ReviewIssue]] = None,
    consistency_issues: Optional[List[ReviewIssue]] = None,
) -> List[ReviewIssue]:
    issues: List[ReviewIssue] = []

    for item in fact_check_results:
        status = item.verification_status.value
        if status not in {"incorrect", "disputed", "unverified", "partial"}:
            continue
        issues.append(
            ReviewIssue(
                issue_type=ReviewIssueType.FACT,
                severity={
                    "incorrect": ReviewSeverity.HIGH,
                    "disputed": ReviewSeverity.MEDIUM,
                    "unverified": ReviewSeverity.MEDIUM,
                    "partial": ReviewSeverity.LOW,
                }.get(status, ReviewSeverity.LOW),
                title=_fact_title(status),
                description=item.claim_content or item.original_text,
                suggestion=_fact_suggestion(item),
                source_excerpt=item.original_text,
                location=item.position,
                confidence=item.confidence,
                metadata={
                    "claim_type": item.claim_type.value,
                    "verification_status": status,
                    "sources": item.sources,
                },
            )
        )

    if structure_match_result:
        missing = [match for match in structure_match_result.section_matches if match.status.value != "matched"]
        if missing:
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.STRUCTURE,
                    severity=ReviewSeverity.MEDIUM,
                    title="结构建议",
                    description="文档结构与模板仍有差异，建议在正文末尾统一补齐缺失部分。",
                    suggestion="请在文末补充缺失章节或合并相关内容，不需要逐段修改格式。",
                    metadata={"anchor_preference": "document_end"},
                )
            )

    if quality_report and not (
        quality_report.overall_score == 0 and all(score.score == 0 for score in quality_report.dimension_scores)
    ):
        quality_findings = []
        for score in quality_report.dimension_scores:
            if score.dimension.value in {"language_expression", "format_compliance"}:
                continue
            if any("评估失败" in weakness or "解析评估结果失败" in weakness for weakness in score.weaknesses):
                continue
            if score.score >= 80:
                continue
            quality_findings.append(score)

        if quality_findings:
            weakest = min(quality_findings, key=lambda item: item.score)
            dimension_names = "、".join(_quality_dimension_name(item.dimension.value) for item in quality_findings)
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.QUALITY,
                    severity=ReviewSeverity.HIGH if weakest.score < 60 else ReviewSeverity.MEDIUM,
                    title="整体质量建议",
                    description=f"以下维度仍需加强：{dimension_names}。",
                    suggestion=(
                        weakest.suggestions[0]
                        if weakest.suggestions
                        else "请补充可验证证据，减少主观判断，并统一前后表述。"
                    ),
                    confidence=max(0.0, min(1.0, weakest.score / 100)),
                    metadata={
                        "dimensions": [item.dimension.value for item in quality_findings],
                        "scores": {item.dimension.value: item.score for item in quality_findings},
                        "anchor_preference": "document_end",
                    },
                )
            )

    if consistency_issues:
        issues.extend(consistency_issues)
    if language_issues:
        issues.extend(language_issues)

    return issues


def build_review_report(
    summary: str,
    recommendations: List[str],
    issues: List[ReviewIssue],
    fact_check_results: List[FactCheckResult],
    structure_match_result: Optional[StructureMatchResult],
    quality_report: Optional[QualityReport],
    metadata: Optional[Dict[str, object]] = None,
) -> ReviewReport:
    metrics = {
        "issue_count": len(issues),
        "high_severity_count": sum(1 for issue in issues if issue.severity == ReviewSeverity.HIGH),
        "fact_check_count": len(fact_check_results),
        "flagged_fact_count": sum(1 for issue in issues if issue.issue_type == ReviewIssueType.FACT),
        "language_issue_count": sum(1 for issue in issues if issue.issue_type == ReviewIssueType.LANGUAGE),
        "consistency_issue_count": sum(1 for issue in issues if issue.issue_type == ReviewIssueType.CONSISTENCY),
        "structure_score": structure_match_result.overall_score if structure_match_result else None,
        "quality_score": quality_report.overall_score if quality_report else None,
        "quality_level": quality_report.overall_level.value if quality_report else None,
    }
    return ReviewReport(
        summary=summary,
        recommendations=recommendations,
        issues=issues,
        metrics=metrics,
        metadata=metadata or {},
    )


def quality_level_to_severity(level: QualityLevel) -> ReviewSeverity:
    if level == QualityLevel.POOR:
        return ReviewSeverity.HIGH
    if level == QualityLevel.NEEDS_IMPROVEMENT:
        return ReviewSeverity.MEDIUM
    return ReviewSeverity.LOW


def _fact_title(status: str) -> str:
    return {
        "incorrect": "事实错误",
        "disputed": "事实存疑",
        "unverified": "事实待核实",
        "partial": "事实部分准确",
    }.get(status, "事实问题")


def _fact_suggestion(item: FactCheckResult) -> str:
    status = item.verification_status.value
    has_sources = bool(item.sources)

    if status in {"incorrect", "disputed"}:
        if has_sources:
            return "检索到的网络信息与原文表述存在冲突，建议依据下列来源核对后改写。"
        return "现有公开信息与原文表述存在冲突，建议补充权威来源后再保留。"

    if status == "partial":
        if has_sources:
            return "检索到的网络信息只能部分支持原文表述，建议依据下列来源补全或修正。"
        return "公开信息只能部分支持该表述，建议补充来源后再保留。"

    if status == "unverified":
        if has_sources:
            return "检索到的网络信息未能直接证实该表述，建议依据下列来源核对后再保留。"
        return "当前未检索到足够公开信息支持该表述，建议补充可验证来源后再保留。"

    return item.suggestion or "请复核该内容。"


def _quality_dimension_name(value: str) -> str:
    return {
        "content_completeness": "内容完整性",
        "logical_clarity": "逻辑清晰度",
        "argumentation_quality": "论证充分性",
        "data_accuracy": "数据准确性",
        "language_expression": "语言表达",
        "format_compliance": "格式规范",
    }.get(value, value)


def _shorten_quality_description(weaknesses: List[str], dimension: str) -> str:
    if not weaknesses:
        return f"{_quality_dimension_name(dimension)}仍需加强。"
    first = weaknesses[0].strip()
    return first.split("；")[0].split("。")[0].strip() or f"{_quality_dimension_name(dimension)}仍需加强。"
