"""
腾讯文档智能审核批注工具

一个基于腾讯文档 + DeepSeek + MCP 的文章审核系统。
支持事实核查、结构匹配、质量评估，并直接在腾讯文档中插入批注。
"""

__version__ = "0.1.0"
__author__ = "Dev Claw"

from .config import Settings, get_settings
from .mcp_client import TencentDocMCPClient
from .deepseek_client import DeepSeekClient

__all__ = [
    "Settings",
    "get_settings",
    "TencentDocMCPClient",
    "DeepSeekClient",
]
