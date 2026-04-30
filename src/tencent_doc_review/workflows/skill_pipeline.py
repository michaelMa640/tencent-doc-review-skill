"""Shared workflow for skill-style document review execution."""

from __future__ import annotations

import platform
import re
import tempfile
import unicodedata
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, List, Optional

from ..access import (
    DownloadFormat,
    DownloadManager,
    DownloadedDocument,
    MCPDocumentClient,
    TencentDocReference,
    UploadTarget,
    UploadManager,
    UploadResult,
)
from ..analyzer.document_analyzer import AnalysisResult, DocumentAnalyzer
from ..config import PROJECT_ROOT, get_effective_debug_output_dir, get_settings
from ..document import (
    AnnotatedWordDocument,
    DocxCompressor,
    WordAnnotation,
    WordAnnotator,
    WordParser,
)
from ..document.word_parser import ParagraphNode, SentenceNode
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
class LocalReviewArtifacts:
    source_path: str
    annotated_word_path: str
    upload_candidate_path: str
    markdown_report_path: str
    annotation_count: int
    review_issue_count: int
    review_summary: str
    compression_applied: bool = False
    compression_result_size: int = 0
    compression_original_size: int = 0
    compression_target_met: bool = True
    debug_bundle_path: str = ""


@dataclass
class AnchorResolution:
    paragraph_index: int
    reliable: bool = False
    strategy: str = "fallback"


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

    def _sanitize_filename_stem(self, value: str, fallback: str = "") -> str:
        sanitized = "".join(char for char in (value or "").strip() if char not in '<>:"/\\|?*').strip().rstrip(".")
        return sanitized or fallback

    def _collect_source_document_stats(self, parsed_document) -> dict[str, int]:
        non_empty_paragraphs = [node for node in parsed_document.paragraphs if node.text.strip()]
        body_paragraphs = [node for node in non_empty_paragraphs if not node.is_heading]
        heading_paragraphs = [node for node in non_empty_paragraphs if node.is_heading]
        body_chars = sum(len(node.text.strip()) for node in body_paragraphs)
        return {
            "paragraph_count": len(parsed_document.paragraphs),
            "non_empty_paragraph_count": len(non_empty_paragraphs),
            "heading_paragraph_count": len(heading_paragraphs),
            "body_paragraph_count": len(body_paragraphs),
            "sentence_count": len(parsed_document.sentences),
            "body_character_count": body_chars,
        }

    def _validate_source_document_content(self, parsed_document, document_title: str) -> None:
        stats = self._collect_source_document_stats(parsed_document)
        has_structured_body = stats["body_paragraph_count"] >= 2 and stats["body_character_count"] >= 120
        has_long_fallback_body = (
            stats["body_paragraph_count"] >= 1
            and stats["body_character_count"] >= 240
            and stats["sentence_count"] >= 4
        )
        if has_structured_body or has_long_fallback_body:
            return
        raise ValueError(
            "Downloaded source document appears incomplete and was not reviewed. "
            f"title={document_title!r}, body_paragraphs={stats['body_paragraph_count']}, "
            f"body_characters={stats['body_character_count']}, sentences={stats['sentence_count']}. "
            "This usually means the Tencent Docs MCP resolved the wrong object from the provided link, "
            "especially for team-space links like docs.qq.com/space/...?...resourceId=.... "
            "Please retry with the real docs.qq.com/doc/... link or confirm the original document object before upload."
        )

    async def review_local_docx(
        self,
        input_path: str | Path,
        title: str = "",
        provider: str = "",
        output_dir: str | Path = "",
        debug_output_dir: str = "",
        max_upload_size_bytes: int = 10 * 1024 * 1024,
    ) -> LocalReviewArtifacts:
        source_path = Path(input_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Input DOCX not found: {source_path}")

        target_dir = Path(output_dir) if output_dir else source_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        parsed_document = self.word_parser.parse(source_path)
        document_title = title or parsed_document.title or source_path.stem
        self._validate_source_document_content(parsed_document, document_title)
        document_text = self._render_document_text(parsed_document.paragraphs)

        request = SkillRequest(
            source_document=TencentDocReference(doc_id=source_path.stem, title=document_title),
            target_location=UploadTarget(
                folder_id="",
                space_id="",
                space_type="personal_space",
                path_hint="",
                display_name="",
            ),
            llm_provider=provider or get_settings().llm_provider,
        )
        review_result = await self._review_document(
            request=request,
            document_text=document_text,
            document_title=document_title,
        )
        review_annotations = self._build_word_annotations(
            parsed_document.paragraphs,
            parsed_document.sentences,
            review_result,
            request,
        )

        output_stem = self._sanitize_filename_stem(document_title, source_path.stem)
        annotated_path = target_dir / f"{output_stem}-annotated.docx"
        annotated = self.word_annotator.annotate(
            source_path=source_path,
            output_path=annotated_path,
            annotations=review_annotations,
            document_title=document_title,
        )
        review_report_path = self._write_markdown_report(annotated.output_path, review_result)

        upload_candidate_path = annotated.output_path
        compression_metadata = {
            "compression_applied": False,
            "compression_result_size": annotated.output_path.stat().st_size,
            "compression_original_size": annotated.output_path.stat().st_size,
            "compression_target_met": True,
        }
        if annotated.output_path.stat().st_size > max_upload_size_bytes:
            compressed_path = annotated.output_path.with_name(f"{annotated.output_path.stem}-compressed.docx")
            compression_result = self.docx_compressor.compress_to_target(
                source_path=annotated.output_path,
                output_path=compressed_path,
                target_max_bytes=max_upload_size_bytes,
            )
            upload_candidate_path = compression_result.output_path
            compression_metadata = {
                "compression_applied": True,
                "compression_result_size": compression_result.compressed_size,
                "compression_original_size": compression_result.original_size,
                "compression_target_met": compression_result.target_met,
            }

        debug_bundle_path = self._write_debug_bundle(
            debug_output_dir=debug_output_dir,
            document_title=document_title,
            source_path=source_path,
            parsed_document=parsed_document,
            review_result=review_result,
            annotations=review_annotations,
            extra_metadata={
                "annotated_word_path": str(annotated.output_path),
                "upload_candidate_path": str(upload_candidate_path),
                "markdown_report_path": str(review_report_path),
                **compression_metadata,
            },
        )

        return LocalReviewArtifacts(
            source_path=str(source_path),
            annotated_word_path=str(annotated.output_path),
            upload_candidate_path=str(upload_candidate_path),
            markdown_report_path=str(review_report_path),
            annotation_count=annotated.annotation_count,
            review_issue_count=len(review_result.review_issues),
            review_summary=review_result.summary,
            debug_bundle_path=debug_bundle_path,
            **compression_metadata,
        )

    async def run(self, client: MCPDocumentClient, request: SkillRequest) -> SkillResponse:
        reference = self._build_source_reference(request)
        downloaded = await self.download_manager.download_via_mcp(
            client=client,
            reference=reference,
            purpose="document",
            download_format=DownloadFormat.DOCX,
        )
        downloaded = self._ensure_stable_local_filename(downloaded, request)

        parsed_document = self.word_parser.parse(downloaded.file_path)
        self._validate_source_document_content(
            parsed_document,
            parsed_document.title or request.source_document.display_name or request.source_document.doc_id,
        )
        document_text = self._render_document_text(parsed_document.paragraphs)
        review_result = await self._review_document(
            request=request,
            document_text=document_text,
            document_title=parsed_document.title or request.source_document.display_name,
        )
        review_annotations = self._build_word_annotations(
            parsed_document.paragraphs,
            parsed_document.sentences,
            review_result,
            request,
        )

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

        debug_bundle_path = self._write_debug_bundle(
            debug_output_dir=request.debug_output_dir,
            document_title=request.source_document.display_name or request.source_document.title or request.source_document.doc_id,
            source_path=downloaded.file_path,
            parsed_document=parsed_document,
            review_result=review_result,
            annotations=review_annotations,
            extra_metadata={
                "annotated_word_path": str(annotated.output_path),
                "upload_candidate_path": str(upload_source_path),
                "markdown_report_path": str(review_report_path),
                "download_source_path": downloaded.metadata.get("source_path", ""),
                **compression_metadata,
            },
        )

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
            annotated_word_path=str(upload_source_path),
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
                "pre_compression_annotated_word_path": str(annotated.output_path),
                "uploaded_local_word_path": str(upload_source_path),
                "review_rules_path": get_default_review_rules_path(),
                "review_structure_template_path": get_default_review_template_path(),
                "debug_bundle_path": debug_bundle_path,
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
        sentences: List[SentenceNode],
        review_result: AnalysisResult,
        request: SkillRequest,
    ) -> List[WordAnnotation]:
        annotations = [self._to_word_annotation(paragraphs, sentences, issue) for issue in review_result.review_issues]
        annotations.extend(self._build_summary_annotations(review_result, request))
        return annotations

    def _to_word_annotation(
        self,
        paragraphs: List[ParagraphNode],
        sentences: List[SentenceNode],
        issue: ReviewIssue,
    ) -> WordAnnotation:
        metadata = dict(issue.metadata) if isinstance(issue.metadata, dict) else {}
        anchor = self._resolve_anchor(paragraphs, sentences, issue)
        comment_text = self._format_issue_comment(issue, metadata)

        if metadata.get("anchor_preference") == "document_end" or anchor.strategy == "document_end":
            metadata["render_mode"] = "summary_block"
            metadata.setdefault("anchor_reason", anchor.strategy)
        elif not anchor.reliable:
            metadata["render_mode"] = "summary_block"
            metadata.setdefault("anchor_reason", anchor.strategy or "unreliable_anchor")

        return WordAnnotation(
            paragraph_index=anchor.paragraph_index,
            title=issue.title,
            comment=comment_text,
            severity=issue.severity.value,
            source_excerpt=issue.source_excerpt,
            metadata=metadata,
        )

    def _build_summary_annotations(
        self,
        review_result: AnalysisResult,
        request: SkillRequest,
    ) -> List[WordAnnotation]:
        annotations: List[WordAnnotation] = [
            WordAnnotation(
                paragraph_index=0,
                title="审核运行情况",
                comment=self._format_runtime_summary(review_result, request),
                severity="low",
                metadata={"render_mode": "summary_block", "anchor_preference": "document_end"},
            )
        ]

        structure_annotation = self._build_structure_summary_annotation(review_result)
        if structure_annotation is not None:
            annotations.append(structure_annotation)

        for fact_comment in self._build_fact_detail_summaries(review_result):
            annotations.append(
                WordAnnotation(
                    paragraph_index=0,
                    title="事实核查详细情况",
                    comment=fact_comment,
                    severity="medium",
                    metadata={"render_mode": "summary_block", "anchor_preference": "document_end"},
                )
            )
        return annotations

    def _build_structure_summary_annotation(self, review_result: AnalysisResult) -> Optional[WordAnnotation]:
        structure_result = review_result.structure_match_result
        if structure_result is None or not structure_result.section_matches:
            return None

        rows = self._build_structure_match_table_rows(review_result)
        matched_count = sum(1 for match in structure_result.section_matches if match.status.value == "matched")
        total_count = len(structure_result.section_matches)
        missing_count = sum(1 for match in structure_result.section_matches if match.status.value != "matched")
        comment_lines = [
            f"模板结构匹配度：{structure_result.overall_score:.1%}",
            f"已覆盖章节：{matched_count}/{total_count}",
        ]
        if missing_count:
            comment_lines.append(f"仍缺失章节：{missing_count} 个")
        else:
            comment_lines.append("模板章节已全部覆盖。")

        return WordAnnotation(
            paragraph_index=0,
            title="结构模板相关性",
            comment="\n".join(comment_lines),
            severity="low",
            metadata={
                "render_mode": "summary_block",
                "anchor_preference": "document_end",
                "summary_table": rows,
            },
        )

    def _build_structure_match_table_rows(self, review_result: AnalysisResult) -> List[List[str]]:
        structure_result = review_result.structure_match_result
        if structure_result is None:
            return []

        rows: List[List[str]] = [["模板章节", "当前文章是否已有", "当前命中章节名", "状态说明"]]
        for match in structure_result.section_matches:
            status = match.status.value
            rows.append(
                [
                    str(match.template_section.title or "").strip(),
                    "✓" if status == "matched" else "✗",
                    str(match.document_section.title if match.document_section else "").strip(),
                    self._describe_structure_match_status(status),
                ]
            )
        return rows

    def _describe_structure_match_status(self, status: str) -> str:
        return {
            "matched": "已覆盖",
            "missing": "缺失",
            "partial": "部分匹配",
            "misplaced": "位置不对应",
            "extra": "额外章节",
        }.get(status, status or "")

    def _format_issue_comment(self, issue: ReviewIssue, metadata: dict) -> str:
        lines: List[str] = []
        description = (issue.description or "").strip()
        if description:
            lines.append(f"问题：{description}")

        suggestion = (issue.suggestion or "").strip()
        if suggestion:
            lines.append(f"建议：{suggestion}")

        trace_lines = self._format_search_trace(metadata.get("search_trace"))
        if trace_lines:
            lines.append("检索痕迹：")
            lines.extend(trace_lines)

        source_lines = self._format_sources(metadata.get("sources"))
        if source_lines:
            lines.append("来源：")
            lines.extend(source_lines)

        return "\n".join(lines).strip()

    def _resolve_runtime_model_label(self, review_result: AnalysisResult, request: SkillRequest) -> str:
        for item in review_result.fact_check_results:
            trace = item.search_trace if isinstance(item.search_trace, dict) else {}
            llm_provider = str(trace.get("llm_provider") or "").strip()
            llm_model = str(trace.get("llm_model") or "").strip()
            if llm_provider or llm_model:
                return " / ".join(part for part in [llm_provider, llm_model] if part)
        return (request.llm_provider or "deepseek").strip().lower()

    def _collect_fact_check_trace_overview(self, review_result: AnalysisResult) -> dict[str, object]:
        traces = [item.search_trace for item in review_result.fact_check_results if isinstance(item.search_trace, dict)]
        mode = ""
        executed_counts: dict[str, int] = {}
        fallback_count = 0
        first_reason = ""
        first_fallback_reason = ""

        for trace in traces:
            if not mode:
                mode = str(trace.get("mode") or "").strip()

            if trace.get("performed"):
                label = self._describe_actual_search_execution(trace)
                if label:
                    executed_counts[label] = executed_counts.get(label, 0) + 1

            if trace.get("fallback_triggered"):
                fallback_count += 1

            if not first_reason:
                first_reason = str(trace.get("reason") or trace.get("error") or "").strip()

            if not first_fallback_reason:
                first_fallback_reason = str(trace.get("fallback_reason") or "").strip()

        return {
            "mode": mode,
            "default_strategy": self._describe_search_strategy(mode),
            "executed_counts": executed_counts,
            "fallback_count": fallback_count,
            "reason": first_reason,
            "fallback_reason": first_fallback_reason,
        }

    def _format_runtime_summary(self, review_result: AnalysisResult, request: SkillRequest) -> str:
        fact_trace_overview = self._collect_fact_check_trace_overview(review_result)
        lines: List[str] = [
            f"审核时间：{review_result.timestamp}",
            f"审核模型：{self._resolve_runtime_model_label(review_result, request)}",
            f"审核过程评分：{self._estimate_process_score(review_result):.0f}/100",
        ]

        if review_result.quality_report is not None:
            lines.append(
                f"- 质量评估：正常，评分 {review_result.quality_report.overall_score:.1f}/100，等级 {review_result.quality_report.overall_level.value}"
            )
        else:
            lines.append("- 质量评估：未生成结果")

        if review_result.structure_match_result is not None:
            lines.append(f"- 结构核对：正常，匹配度 {review_result.structure_match_result.overall_score:.1%}")
        else:
            lines.append("- 结构核对：未生成结果")

        fact_fallback_count = sum(
            1
            for item in review_result.fact_check_results
            if any("LLM verification failed" in evidence for evidence in item.evidence)
        )
        fact_search_count = sum(1 for item in review_result.fact_check_results if item.search_trace.get("performed"))
        fact_line = (
            f"- 事实核查：{'正常' if review_result.fact_check_results else '未生成结果'}，"
            f"核查 {len(review_result.fact_check_results)} 条，实际联网检索 {fact_search_count} 条，LLM fallback {fact_fallback_count} 条"
        )
        lines.append(fact_line)
        if fact_trace_overview["default_strategy"]:
            lines.append(f"- 默认联网策略：{fact_trace_overview['default_strategy']}")
        executed_counts = fact_trace_overview["executed_counts"] if isinstance(fact_trace_overview["executed_counts"], dict) else {}
        if executed_counts:
            executed_summary = "，".join(f"{label} {count} 条" for label, count in executed_counts.items())
            lines.append(f"- 本次联网执行：{executed_summary}")
        elif review_result.fact_check_results:
            lines.append("- 本次联网执行：未执行联网检索")
        if int(fact_trace_overview["fallback_count"] or 0) > 0:
            lines.append(f"- 联网回退：发生 {fact_trace_overview['fallback_count']} 次")
        if fact_trace_overview["fallback_reason"]:
            lines.append(f"- 回退原因：{fact_trace_overview['fallback_reason']}")
        if review_result.fact_check_results and fact_search_count == 0 and fact_trace_overview["reason"]:
            lines.append(f"- 未联网原因：{fact_trace_overview['reason']}")

        language_fallback_count = sum(
            1 for item in review_result.language_issues if str(item.metadata.get('fallback_reason') or '').strip()
        )
        lines.append(
            f"- 语言审核：{'正常' if review_result.language_issues or language_fallback_count == 0 else '未生成结果'}，"
            f"发现 {len(review_result.language_issues)} 条，fallback {language_fallback_count} 条"
        )
        lines.append(f"- 矛盾检查：发现 {len(review_result.consistency_issues)} 条")
        return "\n".join(lines)

    def _estimate_process_score(self, review_result: AnalysisResult) -> float:
        score = 100.0
        if review_result.structure_match_result is None:
            score -= 15
        if review_result.quality_report is None:
            score -= 40
        elif review_result.quality_report.overall_score <= 0:
            score -= 35
        elif review_result.quality_report.overall_score <= 1:
            score -= 50
        elif review_result.quality_report.overall_score < 40:
            score -= 25
        fact_fallback_count = sum(
            1
            for item in review_result.fact_check_results
            if any("LLM verification failed" in evidence for evidence in item.evidence)
        )
        fact_search_count = sum(1 for item in review_result.fact_check_results if item.search_trace.get("performed"))
        if review_result.fact_check_results and fact_search_count == 0:
            score -= 20
        if not review_result.fact_check_results:
            score -= 25
        score -= min(20, fact_fallback_count * 5)
        language_fallback_count = sum(
            1 for item in review_result.language_issues if str(item.metadata.get("fallback_reason") or "").strip()
        )
        if not review_result.language_issues and review_result.quality_report is not None and review_result.quality_report.overall_score <= 1:
            score -= 10
        score -= min(15, language_fallback_count * 5)
        if review_result.quality_report is None and not review_result.fact_check_results and not review_result.language_issues:
            score = min(score, 10.0)
        return max(0.0, min(100.0, score))

    def _build_fact_detail_summaries(self, review_result: AnalysisResult) -> List[str]:
        summaries: List[str] = []
        flagged_results = [
            item
            for item in review_result.fact_check_results
            if item.verification_status.value in {"incorrect", "disputed", "unverified", "partial"}
        ]
        for item in flagged_results:
            lines = [
                f"原文：{item.original_text or item.claim_content}",
                f"结论：{self._fact_status_label(item.verification_status.value)}",
            ]
            trace_lines = self._format_search_trace(item.search_trace)
            if trace_lines:
                lines.append("检索痕迹：")
                lines.extend(trace_lines)
            conflict_point = self._build_conflict_point(item)
            if conflict_point:
                label = "冲突点" if item.verification_status.value in {"incorrect", "disputed", "partial", "unverified"} else "核查依据"
                lines.append(f"{label}：{conflict_point}")
            if item.sources:
                lines.append("搜索源：")
                for source_index, source in enumerate(item.sources, start=1):
                    title = str(source.get("title") or "来源").strip()
                    url = str(source.get("url") or "").strip()
                    snippet = str(source.get("snippet") or "").strip()
                    lines.append(f"来源{source_index}：{title}" + (f" - {url}" if url else ""))
                    if snippet:
                        lines.append(f"搜索源原文：{snippet}")
            summaries.append("\n".join(lines).strip())
        return summaries

    def _fact_status_label(self, status: str) -> str:
        return {
            "incorrect": "发现网络信息与原文冲突",
            "disputed": "发现网络信息与原文存在冲突",
            "partial": "网络信息仅能部分支持原文",
            "unverified": "网络信息未能直接证实原文",
            "confirmed": "未发现明显冲突",
        }.get(status, status)

    def _build_conflict_point(self, item: object) -> str:
        suggestion = str(getattr(item, "suggestion", "") or "").strip()
        if suggestion:
            return suggestion
        evidence = getattr(item, "evidence", None) or []
        if evidence:
            return str(evidence[0]).strip()
        return ""

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

    def _format_search_trace(self, search_trace: object) -> List[str]:
        if not isinstance(search_trace, dict):
            return []
        strategy = self._describe_search_strategy(str(search_trace.get("mode") or "").strip())
        actual_execution = self._describe_actual_search_execution(search_trace)
        llm_provider = str(search_trace.get("llm_provider") or "").strip()
        llm_model = str(search_trace.get("llm_model") or "").strip()

        if not search_trace.get("performed"):
            lines: List[str] = []
            reason = str(search_trace.get("reason") or search_trace.get("error") or "").strip()
            fallback_reason = str(search_trace.get("fallback_reason") or "").strip()
            if strategy:
                lines.append(f"- 默认联网策略：{strategy}")
            lines.append("- 本次实际执行：未执行联网检索")
            if "native_supported" in search_trace:
                lines.append(f"- 模型原生搜索能力：{'可用' if search_trace.get('native_supported') else '不可用'}")
            if fallback_reason:
                lines.append(f"- 模型原生阶段结果：{fallback_reason}")
            if reason:
                lines.append(f"- 未联网原因：{reason}")
            if llm_provider or llm_model:
                model_label = " / ".join(item for item in [llm_provider, llm_model] if item)
                lines.append(f"- 当前审核模型：{model_label}")
            return lines

        provider = str(search_trace.get("provider") or "unknown").strip()
        raw_count = int(search_trace.get("raw_count") or 0)
        filtered_count = int(search_trace.get("filtered_count") or 0)
        lines: List[str] = []
        if strategy:
            lines.append(f"- 默认联网策略：{strategy}")
        if actual_execution:
            lines.append(f"- 本次实际执行：{actual_execution}")
        lines.append(f"- 已联网检索：{provider}，候选 {raw_count} 条，采纳 {filtered_count} 条")
        actual_mode = str(search_trace.get("actual_mode") or "").strip()
        mode = str(search_trace.get("mode") or "").strip()
        if llm_provider or llm_model:
            model_label = " / ".join(item for item in [llm_provider, llm_model] if item)
            lines.append(f"- 当前审核模型：{model_label}")
        tool_type = str(search_trace.get("tool_type") or "").strip()
        if tool_type:
            lines.append(f"- 原生搜索工具：{tool_type}")
        if search_trace.get("fallback_triggered"):
            fallback_from = str(search_trace.get("fallback_from") or "unknown").strip()
            fallback_reason = str(search_trace.get("fallback_reason") or "").strip()
            lines.append(f"- 已触发 fallback：{fallback_from} -> {actual_mode or provider}")
            if fallback_reason:
                lines.append(f"- fallback 原因：{fallback_reason}")
        error = str(search_trace.get("error") or "").strip()
        if error:
            lines.append(f"- 检索异常：{error}")
        return lines

    def _describe_search_strategy(self, mode: str) -> str:
        normalized = (mode or "").strip().lower()
        return {
            "auto": "模型原生 web search -> Tavily",
            "native": "仅模型原生 web search",
            "api": "仅 Tavily API",
            "offline": "关闭联网核查",
        }.get(normalized, "")

    def _describe_actual_search_execution(self, search_trace: dict) -> str:
        if not isinstance(search_trace, dict):
            return ""
        actual_mode = str(search_trace.get("actual_mode") or "").strip().lower()
        provider = str(search_trace.get("provider") or "").strip().lower()
        if actual_mode == "native":
            return "模型原生 web search"
        if actual_mode == "api":
            return "Tavily API"
        if provider == "openai":
            return "模型原生 web search"
        if provider == "tavily":
            return "Tavily API"
        if actual_mode == "offline":
            return "离线模式"
        return ""

    def _resolve_paragraph_index(self, paragraphs: List[ParagraphNode], issue: ReviewIssue) -> int:
        return self._resolve_anchor(paragraphs, [], issue).paragraph_index

    def _resolve_anchor(
        self,
        paragraphs: List[ParagraphNode],
        sentences: List[SentenceNode],
        issue: ReviewIssue,
    ) -> AnchorResolution:
        visible_paragraphs = [paragraph for paragraph in paragraphs if paragraph.text.strip()]
        if not visible_paragraphs:
            return AnchorResolution(paragraph_index=0, reliable=False, strategy="fallback")

        non_heading_paragraphs = [paragraph for paragraph in visible_paragraphs if not paragraph.is_heading]
        candidate_pool = non_heading_paragraphs or visible_paragraphs

        location = issue.location if isinstance(issue.location, dict) else {}
        location_index = location.get("paragraph_index")
        preferred_paragraph = None
        if isinstance(location_index, int) and 0 <= location_index < len(visible_paragraphs):
            preferred_paragraph = visible_paragraphs[location_index]

        source_excerpt = issue.source_excerpt.strip()
        normalized_excerpt = self._normalize_text(source_excerpt)

        sentence_match = self._find_sentence_match(sentences, normalized_excerpt, preferred_paragraph)
        if sentence_match is not None:
            return AnchorResolution(paragraph_index=sentence_match, reliable=True, strategy="sentence_match")

        if source_excerpt and preferred_paragraph is not None:
            preferred_text = self._normalize_text(preferred_paragraph.text)
            if normalized_excerpt and normalized_excerpt in preferred_text and not preferred_paragraph.is_heading:
                return AnchorResolution(paragraph_index=preferred_paragraph.index, reliable=True, strategy="preferred_exact")
            if normalized_excerpt and preferred_text == normalized_excerpt:
                return AnchorResolution(paragraph_index=preferred_paragraph.index, reliable=True, strategy="preferred_exact")

        if source_excerpt:
            for paragraph in candidate_pool:
                if paragraph.text.strip() == source_excerpt:
                    return AnchorResolution(paragraph_index=paragraph.index, reliable=True, strategy="exact")

        if normalized_excerpt:
            substring_match = self._find_best_substring_match(candidate_pool, normalized_excerpt, preferred_paragraph)
            if substring_match is not None:
                return AnchorResolution(paragraph_index=substring_match.index, reliable=True, strategy="substring")

            fuzzy_sentence_match = self._find_best_fuzzy_sentence_match(
                sentences,
                normalized_excerpt,
                preferred_paragraph,
            )
            if fuzzy_sentence_match is not None:
                return AnchorResolution(
                    paragraph_index=fuzzy_sentence_match,
                    reliable=True,
                    strategy="fuzzy_sentence_match",
                )

            fuzzy_paragraph_match = self._find_best_fuzzy_paragraph_match(
                candidate_pool,
                normalized_excerpt,
                preferred_paragraph,
            )
            if fuzzy_paragraph_match is not None:
                return AnchorResolution(
                    paragraph_index=fuzzy_paragraph_match.index,
                    reliable=True,
                    strategy="fuzzy_paragraph_match",
                )

        if issue.metadata.get("anchor_preference") == "document_end":
            return AnchorResolution(paragraph_index=visible_paragraphs[-1].index, reliable=False, strategy="document_end")

        if preferred_paragraph is not None and not preferred_paragraph.is_heading:
            return AnchorResolution(
                paragraph_index=preferred_paragraph.index,
                reliable=False,
                strategy="preferred_approximate",
            )

        fallback = candidate_pool[-1] if candidate_pool else visible_paragraphs[-1]
        return AnchorResolution(paragraph_index=fallback.index, reliable=False, strategy="fallback")

    def _write_markdown_report(self, annotated_output_path: Path, review_result: AnalysisResult) -> str:
        report_path = annotated_output_path.with_suffix(".review.md")
        report_path.write_text(ReportGenerator().render(review_result, "markdown"), encoding="utf-8")
        return str(report_path)

    def _write_debug_bundle(
        self,
        debug_output_dir: str,
        document_title: str,
        source_path: Path,
        parsed_document,
        review_result: AnalysisResult,
        annotations: List[WordAnnotation],
        extra_metadata: dict,
    ) -> str:
        settings = get_settings()
        bundle_root = Path(get_effective_debug_output_dir(debug_output_dir)).expanduser()
        bundle_root.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        provider = (settings.llm_provider or "unknown").strip().lower()
        run_name = f"tdr-debug-{run_id}-{self._sanitize_filename_stem(document_title, source_path.stem)}-{provider}.json"
        bundle_path = bundle_root / run_name

        payload = {
            "bundle_version": 1,
            "redaction_notice": "This debug bundle is intended for issue uploads. Local paths, usernames, and docs.qq.com document IDs are redacted.",
            "document_title": document_title,
            "source_path": self._redact_for_issue(str(source_path)),
            "generated_at": datetime.now().isoformat(),
            "config_snapshot": {
                "llm_provider": settings.llm_provider,
                "review_rules_path": get_default_review_rules_path(),
                "review_structure_template_path": get_default_review_template_path(),
                "review_debug_output_dir": settings.review_debug_output_dir,
            },
            "parsed_document": {
                "paragraphs": [self._build_issue_safe_paragraph_payload(item) for item in parsed_document.paragraphs],
                "sentences": [self._build_issue_safe_sentence_payload(item) for item in parsed_document.sentences],
            },
            "analysis_result": self._redact_for_issue(review_result.to_dict()),
            "annotations": self._redact_for_issue([asdict(item) for item in annotations]),
            "artifacts": self._redact_for_issue(extra_metadata),
        }
        bundle_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(bundle_path)

    def _build_issue_safe_paragraph_payload(self, paragraph: ParagraphNode) -> dict[str, Any]:
        payload = asdict(paragraph)
        text = payload.pop("text", "")
        payload["text_preview"] = self._preview_text(text)
        payload["text_length"] = len(text)
        return self._redact_for_issue(payload)

    def _build_issue_safe_sentence_payload(self, sentence: SentenceNode) -> dict[str, Any]:
        payload = asdict(sentence)
        text = payload.pop("text", "")
        payload["text_preview"] = self._preview_text(text)
        payload["text_length"] = len(text)
        return self._redact_for_issue(payload)

    def _preview_text(self, text: str, max_chars: int = 220) -> str:
        compact = re.sub(r"\s+", " ", (text or "").strip())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 1] + "…"

    def _redact_for_issue(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._redact_for_issue(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_for_issue(item) for item in value]
        if isinstance(value, tuple):
            return [self._redact_for_issue(item) for item in value]
        if isinstance(value, str):
            return self._redact_string(value)
        return value

    def _redact_string(self, value: str) -> str:
        redacted = value or ""

        substitutions = [
            (str(Path.home()), "<HOME>"),
            (str(Path(tempfile.gettempdir())), "<TMP>"),
            (str(Path.cwd()), "<CWD>"),
            (str(PROJECT_ROOT), "<PROJECT_ROOT>"),
            (str(Path(sys.executable).resolve()) if sys.executable else "", "<PYTHON_EXECUTABLE>"),
        ]

        for original, replacement in substitutions:
            if original:
                redacted = redacted.replace(original, replacement)

        redacted = re.sub(
            r"(?i)https://docs\.qq\.com/(doc|sheet|slide|desktop|space)/[A-Za-z0-9$._-]+",
            lambda match: f"https://docs.qq.com/{match.group(1)}/<DOC_ID>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([A-Za-z]:\\Users\\)[^\\]+",
            r"\1<USER>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(/Users/)[^/]+",
            r"\1<USER>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(token|api[_-]?key|secret)\s*[:=]\s*['\"]?([A-Za-z0-9._\-]{8,})['\"]?",
            r"\1=<REDACTED>",
            redacted,
        )
        return redacted

    def _render_document_text(self, paragraphs: List[ParagraphNode]) -> str:
        lines: List[str] = []
        for paragraph in paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            lines.append(text)
        return "\n\n".join(lines)

    def _build_remote_filename(self, request: SkillRequest, suffix: str) -> str:
        base_title = (request.source_document.title or request.source_document.doc_id).strip()
        sanitized = self._sanitize_filename_stem(base_title, request.source_document.doc_id)
        return f"{sanitized}-批注版{suffix}"

    def _ensure_stable_local_filename(self, downloaded: DownloadedDocument, request: SkillRequest) -> DownloadedDocument:
        source_title = (request.source_document.title or request.source_document.doc_id).strip()
        sanitized_title = self._sanitize_filename_stem(source_title)
        if not sanitized_title:
            return downloaded

        target_path = downloaded.file_path.with_name(f"{sanitized_title}{downloaded.file_path.suffix}")
        if downloaded.file_path == target_path:
            return downloaded

        if target_path.exists():
            target_path.unlink()
        original_path = downloaded.file_path
        downloaded.file_path.replace(target_path)
        metadata = dict(downloaded.metadata)
        metadata.setdefault("renamed_from", str(original_path))
        metadata["stable_local_filename"] = target_path.name
        return DownloadedDocument(
            reference=downloaded.reference,
            file_path=target_path,
            download_format=downloaded.download_format,
            filename=target_path.name,
            purpose=downloaded.purpose,
            metadata=metadata,
        )

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "")
        compact: List[str] = []
        for char in normalized:
            if char.isspace():
                continue
            category = unicodedata.category(char)
            if category.startswith(("P", "S", "C")):
                continue
            compact.append(char.lower())
        return "".join(compact)
        stripped = re.sub(r"\s+", "", text).lower()
        return re.sub(r"[:：，,。.;；!?！？、“”\"'‘’（）()\[\]{}<>《》#*_\-—/]+", "", stripped)

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

    def _find_sentence_match(
        self,
        sentences: List[SentenceNode],
        normalized_excerpt: str,
        preferred_paragraph: Optional[ParagraphNode],
    ) -> Optional[int]:
        if not normalized_excerpt or not sentences:
            return None

        candidates: List[tuple[int, int, int, int]] = []
        for order, sentence in enumerate(sentences):
            if sentence.is_heading:
                continue
            normalized_text = self._normalize_text(sentence.text)
            if not normalized_text:
                continue
            position = normalized_text.find(normalized_excerpt)
            if position < 0 and normalized_excerpt.find(normalized_text) < 0:
                continue
            distance = abs(sentence.paragraph_index - preferred_paragraph.index) if preferred_paragraph is not None else 0
            candidates.append((distance, position if position >= 0 else 0, order, sentence.paragraph_index))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][3]

    def _find_best_fuzzy_paragraph_match(
        self,
        paragraphs: List[ParagraphNode],
        normalized_excerpt: str,
        preferred_paragraph: Optional[ParagraphNode],
    ) -> Optional[ParagraphNode]:
        if not normalized_excerpt:
            return None

        candidates: List[tuple[float, int, int, ParagraphNode]] = []
        for order, paragraph in enumerate(paragraphs):
            normalized_text = self._normalize_text(paragraph.text)
            if not normalized_text:
                continue
            ratio = SequenceMatcher(None, normalized_excerpt, normalized_text).ratio()
            if ratio < 0.78:
                continue
            distance = abs(paragraph.index - preferred_paragraph.index) if preferred_paragraph is not None else 0
            candidates.append((ratio, distance, order, paragraph))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        return candidates[0][3]

    def _find_best_fuzzy_sentence_match(
        self,
        sentences: List[SentenceNode],
        normalized_excerpt: str,
        preferred_paragraph: Optional[ParagraphNode],
    ) -> Optional[int]:
        if not normalized_excerpt:
            return None

        candidates: List[tuple[float, int, int, int]] = []
        for order, sentence in enumerate(sentences):
            if sentence.is_heading:
                continue
            normalized_text = self._normalize_text(sentence.text)
            if not normalized_text:
                continue
            ratio = SequenceMatcher(None, normalized_excerpt, normalized_text).ratio()
            if ratio < 0.78:
                continue
            distance = abs(sentence.paragraph_index - preferred_paragraph.index) if preferred_paragraph is not None else 0
            candidates.append((ratio, distance, order, sentence.paragraph_index))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        return candidates[0][3]
