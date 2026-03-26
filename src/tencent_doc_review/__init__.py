"""Tencent document review toolkit."""

__version__ = "0.1.0"
__author__ = "Michael Ma"

from .config import Settings, get_settings
from .access import (
    DownloadFormat,
    DownloadManager,
    DownloadPlan,
    DownloadedDocument,
    MCPDocumentClient,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadManager,
    UploadPlan,
    UploadResult,
    UploadTarget,
)
from .deepseek_client import DeepSeekClient
from .document import (
    AnnotatedWordDocument,
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
    "DownloadManager",
    "DownloadPlan",
    "DownloadedDocument",
    "MCPDocumentClient",
    "MCPDownloadPayload",
    "MCPUploadPayload",
    "TencentDocReference",
    "UploadManager",
    "UploadPlan",
    "UploadResult",
    "UploadTarget",
    "AnnotatedWordDocument",
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
