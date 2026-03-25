"""Append a fixed review block back into Tencent Docs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..analyzer.document_analyzer import AnalysisResult
from ..tencent_doc_client import TencentDocClient


@dataclass
class DocAppendWriter:
    """Write review results into a fixed append-only block."""

    block_title: str = "AI 审核建议"

    async def write(self, client: TencentDocClient, file_id: str, result: AnalysisResult) -> Dict[str, Any]:
        block = self.render_block(result)
        return await client.append_review_block(file_id=file_id, block_markdown=block)

    def render_block(self, result: AnalysisResult) -> str:
        lines = [
            "",
            f"## {self.block_title}",
            "",
            f"- 文档标题: {result.document_title or result.document_id or '未命名文档'}",
            f"- 审核时间: {result.timestamp}",
            "",
            "### 摘要",
            "",
            result.summary or "无摘要。",
            "",
        ]

        if result.recommendations:
            lines.extend(["### 建议", ""])
            for item in result.recommendations:
                lines.append(f"- {item}")
            lines.append("")

        if result.review_issues:
            lines.extend(["### 关键问题", ""])
            for issue in result.review_issues[:10]:
                lines.append(
                    f"- [{issue.severity.value}] {issue.issue_type.value}: {issue.title} | {issue.suggestion or issue.description}"
                )
            lines.append("")

        lines.append("---")
        return "\n".join(lines).strip() + "\n"
