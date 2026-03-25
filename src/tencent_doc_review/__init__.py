"""Tencent document review toolkit."""

__version__ = "0.1.0"
__author__ = "Michael Ma"

from .config import Settings, get_settings
from .deepseek_client import DeepSeekClient
from .domain import ReviewIssue, ReviewIssueType, ReviewReport, ReviewSeverity
from .llm import LLMClient, LLMResponse, SUPPORTED_PROVIDERS, UsageInfo, create_llm_client
from .tencent_doc_client import DriveItem, TencentDocClient, TencentDocMCPClient

__all__ = [
    "Settings",
    "get_settings",
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
