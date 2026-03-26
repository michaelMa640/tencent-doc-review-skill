"""Command-bridge MCP clients for OpenClaw / Claude Code integration."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .mcp_adapter import (
    DownloadFormat,
    MCPDownloadPayload,
    MCPUploadPayload,
    TencentDocReference,
    UploadTarget,
)


@dataclass
class MCPBridgeConfig:
    """Runtime configuration for an external MCP bridge command."""

    client_name: str
    executable: str
    args: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    env: Dict[str, str] = field(default_factory=dict)


class MCPBridgeError(RuntimeError):
    """Raised when an external MCP bridge fails or returns invalid data."""


class CommandMCPClient:
    """Bridge MCP operations through a local command that exchanges JSON over stdio."""

    def __init__(self, config: MCPBridgeConfig) -> None:
        self.config = config

    async def export_document(
        self,
        reference: TencentDocReference,
        download_format: DownloadFormat = DownloadFormat.DOCX,
    ) -> MCPDownloadPayload:
        payload = await self._invoke(
            action="export_document",
            payload={
                "reference": self._reference_to_dict(reference),
                "download_format": download_format.value,
            },
        )
        return MCPDownloadPayload(
            reference=reference,
            format=DownloadFormat(payload.get("format", download_format.value)),
            filename=payload.get("filename") or f"{reference.doc_id}.{download_format.value}",
            content_bytes=self._decode_content_bytes(payload.get("content_bytes")),
            text_content=str(payload.get("text_content", "")),
            source_path=Path(payload["source_path"]) if payload.get("source_path") else None,
            metadata=dict(payload.get("metadata", {})),
        )

    async def upload_document(
        self,
        local_path: Path,
        target: UploadTarget,
        remote_filename: str,
    ) -> MCPUploadPayload:
        payload = await self._invoke(
            action="upload_document",
            payload={
                "local_path": str(Path(local_path)),
                "remote_filename": remote_filename,
                "target": self._target_to_dict(target),
            },
        )
        return MCPUploadPayload(
            target=target,
            uploaded_name=payload.get("uploaded_name") or remote_filename,
            remote_file_id=str(payload.get("remote_file_id", "")),
            remote_url=str(payload.get("remote_url", "")),
            metadata=dict(payload.get("metadata", {})),
        )

    async def _invoke(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = {
            "client": self.config.client_name,
            "action": action,
            "payload": payload,
        }
        completed = await asyncio.wait_for(
            asyncio.to_thread(
                subprocess.run,
                [self.config.executable, *self.config.args],
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    **self.config.env,
                },
            ),
            timeout=self.config.timeout_seconds,
        )
        if completed.returncode != 0:
            raise MCPBridgeError(
                f"{self.config.client_name} MCP bridge failed "
                f"(exit={completed.returncode}, stderr={completed.stderr.strip()})"
            )

        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise MCPBridgeError(
                f"{self.config.client_name} MCP bridge returned invalid JSON"
            ) from exc

        if not response.get("success", True):
            raise MCPBridgeError(
                f"{self.config.client_name} MCP bridge returned error: {response.get('error', 'unknown error')}"
            )

        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPBridgeError(f"{self.config.client_name} MCP bridge returned no result payload")
        return result

    def _reference_to_dict(self, reference: TencentDocReference) -> Dict[str, Any]:
        return {
            "doc_id": reference.doc_id,
            "title": reference.title,
            "folder_id": reference.folder_id,
            "space_id": reference.space_id,
            "url": reference.url,
            "doc_type": reference.doc_type,
            "metadata": dict(reference.metadata),
        }

    def _target_to_dict(self, target: UploadTarget) -> Dict[str, Any]:
        return {
            "folder_id": target.folder_id,
            "space_id": target.space_id,
            "space_type": target.space_type,
            "path_hint": target.path_hint,
            "display_name": target.display_name,
            "metadata": dict(target.metadata),
        }

    def _decode_content_bytes(self, value: Any) -> bytes:
        if value is None:
            return b""
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, bytes):
            return value
        raise MCPBridgeError(f"{self.config.client_name} MCP bridge returned unsupported content_bytes")


def build_bridge_config(
    client_name: str,
    executable: str,
    args_text: str = "",
    timeout_seconds: int = 120,
    env: Optional[Mapping[str, str]] = None,
) -> MCPBridgeConfig:
    """Build a normalized bridge config from environment-driven string values."""

    return MCPBridgeConfig(
        client_name=client_name,
        executable=executable,
        args=shlex.split(args_text, posix=os.name != "nt"),
        timeout_seconds=timeout_seconds,
        env=dict(env or {}),
    )
