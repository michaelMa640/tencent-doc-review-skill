"""Report rendering helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..analyzer.document_analyzer import AnalysisResult


@dataclass
class ReportGenerator:
    """Render analysis results into external report formats."""

    def render(self, result: AnalysisResult, output_format: str = "markdown") -> str:
        normalized = output_format.lower()
        if normalized == "markdown":
            return result.to_markdown()
        if normalized == "json":
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        if normalized == "html":
            return self._to_html(result)
        raise ValueError(f"Unsupported report format: {output_format}")

    def _to_html(self, result: AnalysisResult) -> str:
        markdown = result.to_markdown()
        escaped = (
            markdown.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<html><head><meta charset='utf-8'><title>Document Review Report</title></head>"
            "<body><pre>"
            f"{escaped}"
            "</pre></body></html>"
        )
