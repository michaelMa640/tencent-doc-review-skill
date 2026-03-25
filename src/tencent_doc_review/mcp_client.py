"""Backward-compatible import shim for older code paths."""

from .tencent_doc_client import Comment, DocumentInfo, TencentDocClient, TencentDocMCPClient

__all__ = ["Comment", "DocumentInfo", "TencentDocClient", "TencentDocMCPClient"]
