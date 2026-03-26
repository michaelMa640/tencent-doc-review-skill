"""Shared workflow for skill-style document review execution."""

from __future__ import annotations

import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..access import (
    DownloadFormat,
    DownloadManager,
    DownloadedDocument,
    MCPDocumentClient,
    TencentDocReference,
    UploadManager,
    UploadResult,
)
from ..document import AnnotatedWordDocument, DocxCompressor, WordAnnotator
from ..skill import SkillRequest, SkillResponse, SkillRuntimeInfo


@dataclass
class SkillPipelineArtifacts:
    """Intermediate files produced by the skill workflow."""

    downloaded_document: DownloadedDocument
    annotated_document: AnnotatedWordDocument
    upload_result: UploadResult


class SkillPipeline:
    """Coordinate MCP download, local Word annotation, and remote upload."""

    def __init__(
        self,
        download_manager: Optional[DownloadManager] = None,
        upload_manager: Optional[UploadManager] = None,
        docx_compressor: Optional[DocxCompressor] = None,
        word_annotator: Optional[WordAnnotator] = None,
    ) -> None:
        self.download_manager = download_manager or DownloadManager()
        self.upload_manager = upload_manager or UploadManager()
        self.docx_compressor = docx_compressor or DocxCompressor()
        self.word_annotator = word_annotator or WordAnnotator()

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

        annotated_path = downloaded.file_path.with_name(f"{downloaded.file_path.stem}-annotated.docx")
        annotated = self.word_annotator.annotate(
            source_path=downloaded.file_path,
            output_path=annotated_path,
            annotations=[],
            document_title=request.source_document.display_name,
        )

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
            runtime=runtime,
            messages=[
                download_message,
                "Generated local annotated Word artifact.",
                "Compressed annotated document before upload." if compression_metadata["compression_applied"] else "Upload size within threshold; compression skipped.",
                "Uploaded annotated document to target location.",
            ],
            metadata={
                "upload_filename": upload_result.remote_filename,
                "keep_local_artifacts": request.keep_local_artifacts,
                "used_text_fallback": used_fallback,
                "download_source_path": downloaded.metadata.get("source_path", ""),
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
