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
    UploadManager,
    UploadResult,
)
from ..document import AnnotatedWordDocument, WordAnnotator
from ..skill import SkillRequest, SkillResponse, SkillRuntimeInfo


@dataclass
class SkillPipelineArtifacts:
    """Intermediate files produced by the skill workflow."""

    downloaded_document: DownloadedDocument
    annotated_document: AnnotatedWordDocument
    upload_result: UploadResult


class SkillPipeline:
    """Coordinate download, local Word annotation, and remote upload."""

    def __init__(
        self,
        download_manager: Optional[DownloadManager] = None,
        upload_manager: Optional[UploadManager] = None,
        word_annotator: Optional[WordAnnotator] = None,
    ) -> None:
        self.download_manager = download_manager or DownloadManager()
        self.upload_manager = upload_manager or UploadManager()
        self.word_annotator = word_annotator or WordAnnotator()

    async def run(
        self,
        client: MCPDocumentClient,
        request: SkillRequest,
    ) -> SkillResponse:
        downloaded = await self.download_manager.download_via_mcp(
            client=client,
            reference=request.source_document,
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

        upload_result = await self.upload_manager.upload_via_mcp(
            client=client,
            local_path=annotated.output_path,
            target=request.target_location,
            remote_filename=annotated.output_path.name,
        )

        runtime = SkillRuntimeInfo(
            platform=platform.system().lower(),
            temp_root=str(Path(tempfile.gettempdir()) / "tencent-doc-review"),
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
                "Downloaded source document through MCP.",
                "Generated local annotated Word artifact.",
                "Uploaded annotated document to target location.",
            ],
            metadata={
                "upload_filename": upload_result.remote_filename,
                "keep_local_artifacts": request.keep_local_artifacts,
            },
        )
