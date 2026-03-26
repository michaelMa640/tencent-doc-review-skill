"""MCP access-layer contracts for Tencent Docs document retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class DownloadFormat(str, Enum):
    """Supported download formats for MCP-driven export."""

    DOCX = "docx"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "txt"


@dataclass
class TencentDocReference:
    """Reference to a Tencent Docs document as seen by the skill layer."""

    doc_id: str
    title: str = ""
    folder_id: str = ""
    space_id: str = ""
    url: str = ""
    doc_type: str = "doc"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.title or self.doc_id


@dataclass
class MCPDownloadPayload:
    """Normalized output of an MCP download/export operation."""

    reference: TencentDocReference
    format: DownloadFormat
    filename: str
    content_bytes: bytes
    source_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UploadTarget:
    """User-selected destination in Tencent Docs space."""

    folder_id: str = ""
    space_id: str = ""
    path_hint: str = ""
    display_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPUploadPayload:
    """Normalized result of an MCP upload operation."""

    target: UploadTarget
    uploaded_name: str
    remote_file_id: str
    remote_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPDocumentClient(Protocol):
    """Protocol for MCP-backed document download clients."""

    async def export_document(
        self,
        reference: TencentDocReference,
        download_format: DownloadFormat = DownloadFormat.DOCX,
    ) -> MCPDownloadPayload:
        """Export a document through MCP and return normalized bytes."""

    async def upload_document(
        self,
        local_path: Path,
        target: UploadTarget,
        remote_filename: str,
    ) -> MCPUploadPayload:
        """Upload a local file through MCP and return normalized remote metadata."""
