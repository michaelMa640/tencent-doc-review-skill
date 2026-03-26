"""Cross-client skill input/output models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..access import TencentDocReference, UploadTarget


@dataclass
class SkillRequest:
    """Unified request contract for OpenClaw / Claude Code skill entrypoints."""

    source_document: TencentDocReference
    target_location: UploadTarget
    template_document: Optional[TencentDocReference] = None
    llm_provider: str = "deepseek"
    output_formats: List[str] = field(default_factory=lambda: ["markdown"])
    keep_local_artifacts: bool = True
    download_directory: str = ""
    max_upload_size_bytes: int = 10 * 1024 * 1024
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class SkillRuntimeInfo:
    """Runtime details that help callers understand local execution behavior."""

    platform: str
    temp_root: str
    cli_entrypoint: str = "tencent-doc-review"
    supports_windows: bool = True
    supports_macos: bool = True


@dataclass
class SkillResponse:
    """Unified response contract for agent-side consumption."""

    success: bool
    source_document: TencentDocReference
    target_location: UploadTarget
    local_word_path: str = ""
    annotated_word_path: str = ""
    remote_file_id: str = ""
    remote_url: str = ""
    generated_reports: Dict[str, str] = field(default_factory=dict)
    runtime: Optional[SkillRuntimeInfo] = None
    messages: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
