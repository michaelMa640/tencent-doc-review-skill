"""Shared workflow for skill-style document review execution."""

from __future__ import annotations

import platform
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
from ..llm.factory import create_llm_client
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
    """Intermediate files produced by the skill workflow."""

    downloaded_document: DownloadedDocument
    annotated_document: AnnotatedWordDocument
    upload_result: UploadResult


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

    async def run(
        self,
        client: MCPDocumentClient,
        request: SkillRequest,
    ) -> SkillResponse:
        reference = self._build_source_reference(request)
        downloaded = await self.download_manager.download_via_mcp(
            client=client,
            reference=reference,
            purpose="document",
            download_format=DownloadFormat.DOCX,
        )

        parsed_document = self.word_parser.parse(downloaded.file_path)
        document_text = "\n\n".join(node.text for node in parsed_document.paragraphs if node.text)
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
            remote_filename=upload_source_path.name,
        )

        runtime = SkillRuntimeInfo(
            platform=platform.system().lower(),
            temp_root=str(Path(tempfile.gettempdir()) / "tencent-doc-review"),
        )

        used_fallback = bool(downloaded.metadata.get("used_text_fallback"))
        download_message = (
            "Downloaded original Word document through MCP."
            if not used_fallback
            else "MCP direct download unavailable; materialized local Word document from fallback text content."
        )

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
                download_message,
                f"Generated local annotated Word artifact with {annotated.annotation_count} review annotations.",
                (
                    "Compressed annotated document before upload."
                    if compression_metadata["compression_applied"]
                    else "Upload size within threshold; compression skipped."
                ),
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
        llm_client = create_llm_client(
            provider=request.llm_provider or settings.llm_provider,
            api_key=settings.llm_api_key or settings.deepseek_api_key,
            base_url=settings.llm_base_url or settings.deepseek_base_url,
            model=settings.llm_model or settings.deepseek_model,
            timeout=settings.request_timeout,
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
        paragraph_index = self._resolve_paragraph_index(paragraphs, issue)
        comment_parts = [issue.description]
        if issue.suggestion:
            comment_parts.append(f"建议：{issue.suggestion}")
        source_links = issue.metadata.get("sources") if isinstance(issue.metadata, dict) else None
        if source_links:
            comment_parts.append(f"来源：{source_links}")
        return WordAnnotation(
            paragraph_index=paragraph_index,
            title=issue.title,
            comment="\n".join(part for part in comment_parts if part),
            severity=issue.severity.value,
            source_excerpt=issue.source_excerpt,
            metadata=issue.metadata,
        )

    def _resolve_paragraph_index(self, paragraphs: List[ParagraphNode], issue: ReviewIssue) -> int:
        location_index = issue.location.get("paragraph_index") if isinstance(issue.location, dict) else None
        if isinstance(location_index, int):
            return location_index

        needles = [
            issue.source_excerpt.strip(),
            issue.description.strip(),
            str(issue.metadata.get("template_section", "")).strip() if isinstance(issue.metadata, dict) else "",
        ]
        for needle in needles:
            if not needle:
                continue
            for paragraph in paragraphs:
                if paragraph.text and needle in paragraph.text:
                    return paragraph.index

        first_heading = next(
            (paragraph.index for paragraph in paragraphs if paragraph.is_heading and paragraph.text),
            None,
        )
        if first_heading is not None:
            return first_heading
        return -1

    def _write_markdown_report(self, annotated_output_path: Path, review_result: AnalysisResult) -> str:
        report_path = annotated_output_path.with_suffix(".review.md")
        report_path.write_text(ReportGenerator().render(review_result, "markdown"), encoding="utf-8")
        return str(report_path)
