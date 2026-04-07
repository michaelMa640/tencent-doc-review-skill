"""Access-layer abstractions for MCP-driven document download/upload workflows."""

from .agent_mcp_client import CommandMCPClient, MCPBridgeConfig, MCPBridgeError, build_bridge_config
from .claude_code_bridge import ClaudeCodeBridgeError, ClaudeCodeBridgeSettings
from .download_manager import DownloadManager, DownloadPlan, DownloadedDocument
from .mcp_adapter import (
    DownloadFormat,
    MCPDocumentClient,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadTarget,
)
from .openclaw_bridge import OpenClawBridgeError, OpenClawBridgeSettings
from .upload_manager import UploadManager, UploadPlan, UploadResult

__all__ = [
    "DownloadFormat",
    "CommandMCPClient",
    "MCPBridgeConfig",
    "MCPBridgeError",
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
    "ClaudeCodeBridgeError",
    "ClaudeCodeBridgeSettings",
    "OpenClawBridgeError",
    "OpenClawBridgeSettings",
    "build_bridge_config",
]
