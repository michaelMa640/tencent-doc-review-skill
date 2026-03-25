"""Unified review result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ReviewSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewIssueType(Enum):
    FACT = "fact"
    STRUCTURE = "structure"
    QUALITY = "quality"


@dataclass
class ReviewIssue:
    issue_type: ReviewIssueType
    severity: ReviewSeverity
    title: str
    description: str
    suggestion: str = ""
    source_excerpt: str = ""
    location: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "suggestion": self.suggestion,
            "source_excerpt": self.source_excerpt,
            "location": self.location,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class ReviewReport:
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    issues: List[ReviewIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "recommendations": self.recommendations,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "metadata": self.metadata,
        }
