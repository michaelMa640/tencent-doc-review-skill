"""Tencent document review toolkit."""

__version__ = "0.1.0"
__author__ = "Michael Ma"

from .config import Settings, get_settings
from .access import (
    CommandMCPClient,
    DownloadFormat,
    DownloadManager,
    DownloadPlan,
    DownloadedDocument,
    MCPBridgeConfig,
    MCPBridgeError,
    MCPDocumentClient,
    MCPDownloadPayload,
    MCPUploadPayload,
    OpenClawBridgeError,
    OpenClawBridgeSettings,
    TencentDocReference,
    UploadManager,
    UploadPlan,
    UploadResult,
    UploadTarget,
    build_bridge_config,
)
from .deepseek_client import DeepSeekClient
from .document import (
    AnnotatedWordDocument,
    DocxCompressionResult,
    DocxCompressor,
    ParagraphNode,
    ParsedWordDocument,
    WordAnnotation,
    WordAnnotator,
    WordParser,
)
from .skill import SkillRequest, SkillResponse, SkillRuntimeInfo
from .workflows import SkillPipeline, SkillPipelineArtifacts
from .domain import ReviewIssue, ReviewIssueType, ReviewReport, ReviewSeverity
from .llm import LLMClient, LLMResponse, SUPPORTED_PROVIDERS, UsageInfo, create_llm_client
from .tencent_doc_client import DriveItem, TencentDocClient, TencentDocMCPClient

__all__ = [
    "Settings",
    "get_settings",
    "DownloadFormat",
    "CommandMCPClient",
    "DownloadManager",
    "DownloadPlan",
    "DownloadedDocument",
    "MCPBridgeConfig",
    "MCPBridgeError",
    "MCPDocumentClient",
    "MCPDownloadPayload",
    "MCPUploadPayload",
    "OpenClawBridgeError",
    "OpenClawBridgeSettings",
    "TencentDocReference",
    "UploadManager",
    "UploadPlan",
    "UploadResult",
    "UploadTarget",
    "build_bridge_config",
    "AnnotatedWordDocument",
    "DocxCompressionResult",
    "DocxCompressor",
    "ParagraphNode",
    "ParsedWordDocument",
    "SkillPipeline",
    "SkillPipelineArtifacts",
    "SkillRequest",
    "SkillResponse",
    "SkillRuntimeInfo",
    "WordAnnotation",
    "WordAnnotator",
    "WordParser",
    "ReviewIssue",
    "ReviewIssueType",
    "ReviewReport",
    "ReviewSeverity",
    "LLMClient",
    "LLMResponse",
    "UsageInfo",
    "SUPPORTED_PROVIDERS",
    "create_llm_client",
    "DriveItem",
    "TencentDocClient",
    "TencentDocMCPClient",
    "DeepSeekClient",
]
