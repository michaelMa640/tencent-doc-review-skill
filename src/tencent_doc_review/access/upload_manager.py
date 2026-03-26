"""Upload planning for annotated Word documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .mcp_adapter import MCPDocumentClient, MCPUploadPayload, UploadTarget


@dataclass
class UploadPlan:
    """Resolved upload destination and filename."""

    local_path: Path
    target: UploadTarget
    remote_filename: str
    overwrite: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class UploadResult:
    """Normalized upload result for skill / CLI layers."""

    local_path: Path
    target: UploadTarget
    remote_filename: str
    remote_file_id: str
    remote_url: str = ""
    metadata: Dict[str, object] = field(default_factory=dict)


class UploadManager:
    """Plan and execute uploads to MCP-backed Tencent Docs destinations."""

    def build_plan(
        self,
        local_path: Path,
        target: UploadTarget,
        remote_filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> UploadPlan:
        path = Path(local_path)
        resolved_name = remote_filename or path.name
        return UploadPlan(
            local_path=path,
            target=target,
            remote_filename=resolved_name,
            overwrite=overwrite,
        )

    async def upload_via_mcp(
        self,
        client: MCPDocumentClient,
        local_path: Path,
        target: UploadTarget,
        remote_filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> UploadResult:
        plan = self.build_plan(
            local_path=local_path,
            target=target,
            remote_filename=remote_filename,
            overwrite=overwrite,
        )
        payload = await client.upload_document(
            local_path=plan.local_path,
            target=plan.target,
            remote_filename=plan.remote_filename,
        )
        metadata = dict(payload.metadata)
        metadata["overwrite"] = overwrite
        return UploadResult(
            local_path=plan.local_path,
            target=plan.target,
            remote_filename=payload.uploaded_name,
            remote_file_id=payload.remote_file_id,
            remote_url=payload.remote_url,
            metadata=metadata,
        )
