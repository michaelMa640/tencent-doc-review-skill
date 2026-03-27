"""Shared workflow for skill-style document review execution."""

from __future__ import annotations

import platform
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..access import (
    DownloadFormat,
    DownloadManager,
    DownloadedDocument,
    MCPDocumentClient,
    TencentDocReference,
    UploadManager,
    UploadResult,
)
from ..analyzer.document_analyzer import AnalysisResult, DocumentAnalyzer
from ..config import get_settings
from ..document import (
    AnnotatedWordDocument,
    DocxCompressor,
    WordAnnotation,
    WordAnnotator,
    WordParser,
)
from ..document.word_parser import ParagraphNode
from ..domain import ReviewIssue
from ..llm.factory import create_llm_client, resolve_llm_settings
from ..skill import SkillRequest, SkillResponse, SkillRuntimeInfo
from ..templates import (
    get_default_review_rules_path,
    get_default_review_template_path,
    read_default_review_rules,
    read_default_review_template,
)
from ..writers import ReportGenerator


@dataclass
class SkillPipelineArtifacts:
    downloaded_document: DownloadedDocument
    annotated_document: AnnotatedWordDocument
    upload_result: UploadResult


@dataclass
class AnchorResolution:
    paragraph_index: int
    reliable: bool = False


class SkillPipeline:
    """Coordinate MCP download, review, local Word annotation, and remote upload."""

    def __init__(
        self,
        download_manager: Optional[DownloadManager] = None,
        upload_manager: Optional[UploadManager] = None,
        docx_compressor: Optional[DocxCompressor] = None,
        word_annotator: Optional[WordAnnotator] = None,
        word_parser: Optional[WordParser] = None,
    ) -> None:
        self.download_manager = download_manager or DownloadManager()
        self.upload_manager = upload_manager or UploadManager()
        self.docx_compressor = docx_compressor or DocxCompressor()
        self.word_annotator = word_annotator or WordAnnotator()
        self.word_parser = word_parser or WordParser()

    async def run(self, client: MCPDocumentClient, request: SkillRequest) -> SkillResponse:
        reference = self._build_source_reference(request)
        downloaded = await self.download_manager.download_via_mcp(
            client=client,
            reference=reference,
            purpose="document",
            download_format=DownloadFormat.DOCX,
        )

        parsed_document = self.word_parser.parse(downloaded.file_path)
        document_text = self._render_document_text(parsed_document.paragraphs)
        review_result = await self._review_document(
            request=request,
            document_text=document_text,
            document_title=parsed_document.title or request.source_document.display_name,
        )
        review_annotations = self._build_word_annotations(parsed_document.paragraphs, review_result.review_issues)

        annotated_path = downloaded.file_path.with_name(f"{downloaded.file_path.stem}-annotated.docx")
        annotated = self.word_annotator.annotate(
            source_path=downloaded.file_path,
            output_path=annotated_path,
            annotations=review_annotations,
            document_title=request.source_document.display_name,
        )

        review_report_path = self._write_markdown_report(annotated.output_path, review_result)

        upload_source_path = annotated.output_path
        compression_metadata = {
            "compression_applied": False,
            "compression_target_bytes": request.max_upload_size_bytes,
            "compression_result_size": annotated.output_path.stat().st_size,
        }
        if annotated.output_path.stat().st_size > request.max_upload_size_bytes:
            compressed_path = annotated.output_path.with_name(f"{annotated.output_path.stem}-compressed.docx")
            compression_result = self.docx_compressor.compress_to_target(
                source_path=annotated.output_path,
                output_path=compressed_path,
                target_max_bytes=request.max_upload_size_bytes,
            )
            upload_source_path = compression_result.output_path
            compression_metadata = {
                "compression_applied": True,
                "compression_target_bytes": request.max_upload_size_bytes,
                "compression_original_size": compression_result.original_size,
                "compression_result_size": compression_result.compressed_size,
                "compression_target_met": compression_result.target_met,
                "compression_max_image_width": compression_result.max_image_width,
                "compression_changed_entries": compression_result.changed_entries,
            }

        upload_result = await self.upload_manager.upload_via_mcp(
            client=client,
            local_path=upload_source_path,
            target=request.target_location,
            remote_filename=self._build_remote_filename(request, upload_source_path.suffix),
        )

        runtime = SkillRuntimeInfo(
            platform=platform.system().lower(),
            temp_root=str(Path(tempfile.gettempdir()) / "tencent-doc-review"),
        )
        used_fallback = bool(downloaded.metadata.get("used_text_fallback"))
        return SkillResponse(
            success=True,
            source_document=request.source_document,
            target_location=request.target_location,
            local_word_path=str(downloaded.file_path),
            annotated_word_path=str(annotated.output_path),
            remote_file_id=upload_result.remote_file_id,
            remote_url=upload_result.remote_url,
            generated_reports={"markdown": review_report_path},
            runtime=runtime,
            messages=[
                "Downloaded original Word document through MCP."
                if not used_fallback
                else "MCP direct download unavailable; materialized local Word document from fallback text content.",
                f"Generated local annotated Word artifact with {annotated.annotation_count} review outputs.",
                "Compressed annotated document before upload."
                if compression_metadata["compression_applied"]
                else "Upload size within threshold; compression skipped.",
                "Uploaded annotated Word document to target location.",
            ],
            metadata={
                "upload_filename": upload_result.remote_filename,
                "keep_local_artifacts": request.keep_local_artifacts,
                "used_text_fallback": used_fallback,
                "download_source_path": downloaded.metadata.get("source_path", ""),
                "annotation_count": annotated.annotation_count,
                "review_issue_count": len(review_result.review_issues),
                "review_summary": review_result.summary,
                "review_rules_path": get_default_review_rules_path(),
                "review_structure_template_path": get_default_review_template_path(),
                **compression_metadata,
            },
        )

    def _build_source_reference(self, request: SkillRequest) -> TencentDocReference:
        metadata = dict(request.source_document.metadata)
        if request.download_directory:
            metadata["preferred_download_dir"] = request.download_directory
        return TencentDocReference(
            doc_id=request.source_document.doc_id,
            title=request.source_document.title,
            folder_id=request.source_document.folder_id,
            space_id=request.source_document.space_id,
            url=request.source_document.url,
            doc_type=request.source_document.doc_type,
            metadata=metadata,
        )

    async def _review_document(
        self,
        request: SkillRequest,
        document_text: str,
        document_title: str,
    ) -> AnalysisResult:
        settings = get_settings()
        provider = (request.llm_provider or settings.llm_provider or "deepseek").strip().lower()
        llm_client = create_llm_client(
            **resolve_llm_settings(
                settings=settings,
                provider=provider,
                timeout=settings.request_timeout,
            )
        )
        try:
            analyzer = DocumentAnalyzer(llm_client=llm_client)
            template_text = read_default_review_template() if request.use_default_template else None
            context = {
                "review_rules": read_default_review_rules(),
                "review_mode": "product_research_default",
            }
            return await analyzer.analyze(
                document_text=document_text,
                template_text=template_text,
                document_title=document_title,
                context=context,
            )
        finally:
            await llm_client.close()

    def _build_word_annotations(
        self,
        paragraphs: List[ParagraphNode],
        issues: List[ReviewIssue],
    ) -> List[WordAnnotation]:
        return [self._to_word_annotation(paragraphs, issue) for issue in issues]

    def _to_word_annotation(self, paragraphs: List[ParagraphNode], issue: ReviewIssue) -> WordAnnotation:
        metadata = dict(issue.metadata) if isinstance(issue.metadata, dict) else {}
        anchor = self._resolve_anchor(paragraphs, issue)
        comment_text = self._format_issue_comment(issue, metadata)

        if metadata.get("anchor_preference") == "document_end":
            metadata["render_mode"] = "summary_block"
        elif not anchor.reliable:
            metadata["render_mode"] = "summary_block"
            metadata.setdefault("anchor_reason", "unreliable_paragraph_match")

        return WordAnnotation(
            paragraph_index=anchor.paragraph_index,
            title=issue.title,
            comment=comment_text,
            severity=issue.severity.value,
            source_excerpt=issue.source_excerpt,
            metadata=metadata,
        )

    def _format_issue_comment(self, issue: ReviewIssue, metadata: dict) -> str:
        lines: List[str] = []
        description = (issue.description or "").strip()
        if description:
            lines.append(f"问题：{description}")

        suggestion = (issue.suggestion or "").strip()
        if suggestion:
            lines.append(f"建议：{suggestion}")

        source_lines = self._format_sources(metadata.get("sources"))
        if source_lines:
            lines.append("来源：")
            lines.extend(source_lines)

        return "\n".join(lines).strip()

    def _format_sources(self, sources: object) -> List[str]:
        if not isinstance(sources, list):
            return []

        lines: List[str] = []
        for index, item in enumerate(sources, start=1):
            if not isinstance(item, dict):
                title = str(item).strip()
                if title:
                    lines.append(f"{index}. {title}")
                continue

            title = str(item.get("title") or "来源").strip()
            url = str(item.get("url") or "").strip()
            if url:
                lines.append(f"{index}. {title} - {url}")
            else:
                lines.append(f"{index}. {title}")
        return lines

    def _resolve_paragraph_index(self, paragraphs: List[ParagraphNode], issue: ReviewIssue) -> int:
        return self._resolve_anchor(paragraphs, issue).paragraph_index

    def _resolve_anchor(self, paragraphs: List[ParagraphNode], issue: ReviewIssue) -> AnchorResolution:
        visible_paragraphs = [paragraph for paragraph in paragraphs if paragraph.text.strip()]
        if not visible_paragraphs:
            return AnchorResolution(paragraph_index=0, reliable=False)

        non_heading_paragraphs = [paragraph for paragraph in visible_paragraphs if not paragraph.is_heading]
        candidate_pool = non_heading_paragraphs or visible_paragraphs

        location = issue.location if isinstance(issue.location, dict) else {}
        location_index = location.get("paragraph_index")
        preferred_paragraph = None
        if isinstance(location_index, int) and 0 <= location_index < len(visible_paragraphs):
            preferred_paragraph = visible_paragraphs[location_index]

        source_excerpt = issue.source_excerpt.strip()
        normalized_excerpt = self._normalize_text(source_excerpt)

        if source_excerpt and preferred_paragraph is not None:
            preferred_text = self._normalize_text(preferred_paragraph.text)
            if normalized_excerpt and normalized_excerpt in preferred_text and not preferred_paragraph.is_heading:
                return AnchorResolution(paragraph_index=preferred_paragraph.index, reliable=True)
            if normalized_excerpt and preferred_text == normalized_excerpt:
                return AnchorResolution(paragraph_index=preferred_paragraph.index, reliable=True)

        if source_excerpt:
            for paragraph in candidate_pool:
                if paragraph.text.strip() == source_excerpt:
                    return AnchorResolution(paragraph_index=paragraph.index, reliable=True)

        if normalized_excerpt:
            substring_match = self._find_best_substring_match(candidate_pool, normalized_excerpt, preferred_paragraph)
            if substring_match is not None:
                return AnchorResolution(paragraph_index=substring_match.index, reliable=True)

            heading_match = self._find_heading_exact_match(visible_paragraphs, normalized_excerpt)
            if heading_match is not None:
                return AnchorResolution(paragraph_index=heading_match.index, reliable=True)

        if issue.metadata.get("anchor_preference") == "document_end":
            return AnchorResolution(paragraph_index=visible_paragraphs[-1].index, reliable=False)

        if preferred_paragraph is not None and not preferred_paragraph.is_heading:
            return AnchorResolution(paragraph_index=preferred_paragraph.index, reliable=False)

        fallback = candidate_pool[-1] if candidate_pool else visible_paragraphs[-1]
        return AnchorResolution(paragraph_index=fallback.index, reliable=False)

    def _write_markdown_report(self, annotated_output_path: Path, review_result: AnalysisResult) -> str:
        report_path = annotated_output_path.with_suffix(".review.md")
        report_path.write_text(ReportGenerator().render(review_result, "markdown"), encoding="utf-8")
        return str(report_path)

    def _render_document_text(self, paragraphs: List[ParagraphNode]) -> str:
        lines: List[str] = []
        for paragraph in paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            if paragraph.heading_level > 0:
                lines.append(f"{'#' * min(paragraph.heading_level, 6)} {text}")
            else:
                lines.append(text)
        return "\n\n".join(lines)

    def _build_remote_filename(self, request: SkillRequest, suffix: str) -> str:
        base_title = (request.source_document.title or request.source_document.doc_id).strip()
        sanitized = "".join(char for char in base_title if char not in '<>:"/\\|?*').strip().rstrip(".")
        if not sanitized:
            sanitized = request.source_document.doc_id
        return f"{sanitized}-批注版{suffix}"

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    def _find_best_substring_match(
        self,
        paragraphs: List[ParagraphNode],
        normalized_excerpt: str,
        preferred_paragraph: Optional[ParagraphNode],
    ) -> Optional[ParagraphNode]:
        if not normalized_excerpt:
            return None

        candidates: List[tuple[int, int, int, ParagraphNode]] = []
        for order, paragraph in enumerate(paragraphs):
            normalized_text = self._normalize_text(paragraph.text)
            position = normalized_text.find(normalized_excerpt)
            if position < 0:
                continue
            distance = abs(paragraph.index - preferred_paragraph.index) if preferred_paragraph is not None else 0
            candidates.append((distance, position, order, paragraph))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][3]

    def _find_heading_exact_match(
        self,
        paragraphs: List[ParagraphNode],
        normalized_excerpt: str,
    ) -> Optional[ParagraphNode]:
        if not normalized_excerpt:
            return None
        for paragraph in paragraphs:
            if paragraph.is_heading and self._normalize_text(paragraph.text) == normalized_excerpt:
                return paragraph
        return None
