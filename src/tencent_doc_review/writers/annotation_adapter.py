"""Annotation adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol

from ..domain import ReviewIssue


@dataclass
class AnnotationPayload:
    title: str
    body: str
    quote_text: str = ""
    location: Dict[str, Any] | None = None


class AnnotationAdapter(Protocol):
    async def write_annotations(self, file_id: str, issues: List[ReviewIssue]) -> Dict[str, Any]:
        ...


class NoopAnnotationAdapter:
    """Placeholder adapter kept for future native comment support."""

    async def write_annotations(self, file_id: str, issues: List[ReviewIssue]) -> Dict[str, Any]:
        return {
            "success": False,
            "mode": "noop",
            "file_id": file_id,
            "count": len(issues),
            "message": "Native annotation writeback is not enabled.",
        }
