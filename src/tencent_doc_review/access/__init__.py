"""Access-layer abstractions for MCP-driven document download/upload workflows."""

from .download_manager import DownloadManager, DownloadPlan, DownloadedDocument
from .mcp_adapter import (
    DownloadFormat,
    MCPDocumentClient,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadTarget,
)
from .upload_manager import UploadManager, UploadPlan, UploadResult

__all__ = [
    "DownloadFormat",
    "MCPDocumentClient",
    "MCPDownloadPayload",
    "MCPUploadPayload",
    "TencentDocReference",
    "UploadTarget",
    "DownloadManager",
    "DownloadPlan",
    "DownloadedDocument",
    "UploadManager",
    "UploadPlan",
    "UploadResult",
]
