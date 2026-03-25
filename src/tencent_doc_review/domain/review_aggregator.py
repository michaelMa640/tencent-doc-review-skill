"""Helpers for aggregating analyzer outputs into unified review models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..analyzer.fact_checker import FactCheckResult
from ..analyzer.quality_evaluator import QualityLevel, QualityReport
from ..analyzer.structure_matcher import StructureMatchResult
from .review_models import ReviewIssue, ReviewIssueType, ReviewReport, ReviewSeverity


def aggregate_review_issues(
    fact_check_results: List[FactCheckResult],
    structure_match_result: Optional[StructureMatchResult],
    quality_report: Optional[QualityReport],
) -> List[ReviewIssue]:
    issues: List[ReviewIssue] = []

    for item in fact_check_results:
        status = item.verification_status.value
        if status not in {"incorrect", "disputed", "unverified", "partial"}:
            continue
        severity = {
            "incorrect": ReviewSeverity.HIGH,
            "disputed": ReviewSeverity.MEDIUM,
            "unverified": ReviewSeverity.MEDIUM,
            "partial": ReviewSeverity.LOW,
        }.get(status, ReviewSeverity.LOW)
        issues.append(
            ReviewIssue(
                issue_type=ReviewIssueType.FACT,
                severity=severity,
                title=f"Fact check: {status}",
                description=item.claim_content or item.original_text,
                suggestion=item.suggestion,
                source_excerpt=item.original_text,
                location=item.position,
                confidence=item.confidence,
                metadata={"claim_type": item.claim_type.value, "verification_status": status},
            )
        )

    if structure_match_result:
        for match in structure_match_result.section_matches:
            if match.status.value == "matched":
                continue
            severity = ReviewSeverity.HIGH if match.status.value == "missing" else ReviewSeverity.MEDIUM
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.STRUCTURE,
                    severity=severity,
                    title=f"Structure: {match.status.value}",
                    description=match.template_section.title,
                    suggestion=match.suggestions[0] if match.suggestions else "",
                    source_excerpt=match.document_section.title if match.document_section else "",
                    confidence=match.similarity,
                    metadata={"template_section": match.template_section.title},
                )
            )

    if quality_report:
        for score in quality_report.dimension_scores:
            if score.score >= 80:
                continue
            severity = ReviewSeverity.HIGH if score.score < 60 else ReviewSeverity.MEDIUM
            description = "; ".join(score.weaknesses) if score.weaknesses else f"{score.dimension.value} needs improvement"
            issues.append(
                ReviewIssue(
                    issue_type=ReviewIssueType.QUALITY,
                    severity=severity,
                    title=f"Quality: {score.dimension.value}",
                    description=description,
                    suggestion=score.suggestions[0] if score.suggestions else "",
                    confidence=max(0.0, min(1.0, score.score / 100)),
                    metadata={"dimension": score.dimension.value, "score": score.score, "level": score.level.value},
                )
            )

    return issues


def build_review_report(
    summary: str,
    recommendations: List[str],
    issues: List[ReviewIssue],
    fact_check_results: List[FactCheckResult],
    structure_match_result: Optional[StructureMatchResult],
    quality_report: Optional[QualityReport],
    metadata: Optional[Dict[str, Any]] = None,
) -> ReviewReport:
    metrics = {
        "issue_count": len(issues),
        "high_severity_count": sum(1 for issue in issues if issue.severity == ReviewSeverity.HIGH),
        "fact_check_count": len(fact_check_results),
        "flagged_fact_count": sum(1 for issue in issues if issue.issue_type == ReviewIssueType.FACT),
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
