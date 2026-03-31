"""Application settings."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - fallback for lean environments
    BaseSettings = None
    Field = None
    SettingsConfigDict = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_OVERRIDE_KEYS = ("TENCENT_DOC_REVIEW_ENV_FILE", "TDR_ENV_FILE")


def _discover_env_file_candidates() -> tuple[str, ...]:
    candidates: list[str] = []

    def add(path: Path | str | None) -> None:
        if not path:
            return
        candidate = str(Path(path).expanduser())
        if candidate not in candidates:
            candidates.append(candidate)

    for key in ENV_OVERRIDE_KEYS:
        add(os.getenv(key))

    cwd = Path.cwd().resolve()
    add(cwd / ".env")
    for parent in list(cwd.parents)[:5]:
        add(parent / ".env")

    add(PROJECT_ROOT / ".env")

    if sys.executable:
        executable_dir = Path(sys.executable).resolve().parent
        add(executable_dir / ".env")
        add(executable_dir.parent / ".env")

    return tuple(candidates)


ENV_FILE_CANDIDATES = _discover_env_file_candidates()


def describe_env_file_candidates() -> list[dict[str, object]]:
    """Return the searched .env locations for diagnostics."""
    return [
        {
            "path": path,
            "exists": Path(path).exists(),
        }
        for path in ENV_FILE_CANDIDATES
    ]


def get_default_debug_output_dir() -> str:
    """Return the default issue-safe debug bundle directory."""
    return str(PROJECT_ROOT / "debug-output")


def get_effective_debug_output_dir(configured_value: str = "") -> str:
    """Resolve the effective debug output directory."""
    candidate = (configured_value or "").strip()
    if candidate:
        return str(Path(candidate).expanduser())
    return get_default_debug_output_dir()


if BaseSettings is not None:

    class Settings(BaseSettings):
        """Application settings loaded from environment variables."""

        model_config = SettingsConfigDict(
            env_file=ENV_FILE_CANDIDATES,
            env_file_encoding="utf-8",
            extra="ignore",
        )

        tencent_docs_token: str = Field(default="", alias="TENCENT_DOCS_TOKEN")
        tencent_docs_client_id: str = Field(default="", alias="TENCENT_DOCS_CLIENT_ID")
        tencent_docs_open_id: str = Field(default="", alias="TENCENT_DOCS_OPEN_ID")
        tencent_docs_base_url: str = Field(default="https://docs.qq.com/openapi")

        llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
        llm_api_key: str = Field(default="", alias="LLM_API_KEY")
        llm_base_url: str = Field(default="https://api.deepseek.com/v1", alias="LLM_BASE_URL")
        llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")

        deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
        deepseek_base_url: str = Field(default="https://api.deepseek.com/v1")
        deepseek_model: str = Field(default="deepseek-chat")

        minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
        minimax_base_url: str = Field(default="https://api.minimaxi.com/v1", alias="MINIMAX_BASE_URL")
        minimax_model: str = Field(default="MiniMax-M2.7", alias="MINIMAX_MODEL")

        search_provider: str = Field(default="disabled", alias="SEARCH_PROVIDER")
        search_api_key: Optional[str] = Field(default=None, alias="SEARCH_API_KEY")
        search_base_url: str = Field(default="https://api.tavily.com/search", alias="SEARCH_BASE_URL")
        search_max_results: int = Field(default=5, alias="SEARCH_MAX_RESULTS")
        search_timeout: int = Field(default=20, alias="SEARCH_TIMEOUT")
        search_depth: str = Field(default="basic", alias="SEARCH_DEPTH")
        search_topic: str = Field(default="general", alias="SEARCH_TOPIC")
        review_rules_template_path: str = Field(default="", alias="REVIEW_RULES_TEMPLATE_PATH")
        review_structure_template_path: str = Field(default="", alias="REVIEW_STRUCTURE_TEMPLATE_PATH")
        batch_size: int = Field(default=5)
        request_timeout: int = Field(default=30)
        tencent_docs_max_retries: int = Field(default=2, alias="TENCENT_DOCS_MAX_RETRIES")
        tencent_docs_retry_delay: float = Field(default=1.0, alias="TENCENT_DOCS_RETRY_DELAY")
        skill_mcp_client: str = Field(default="mock", alias="SKILL_MCP_CLIENT")
        mcp_bridge_timeout: int = Field(default=120, alias="MCP_BRIDGE_TIMEOUT")
        openclaw_mcp_bridge_executable: str = Field(default="", alias="OPENCLAW_MCP_BRIDGE_EXECUTABLE")
        openclaw_mcp_bridge_args: str = Field(default="", alias="OPENCLAW_MCP_BRIDGE_ARGS")
        claude_code_mcp_bridge_executable: str = Field(default="", alias="CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE")
        claude_code_mcp_bridge_args: str = Field(default="", alias="CLAUDE_CODE_MCP_BRIDGE_ARGS")
        review_debug_output_dir: str = Field(default="", alias="REVIEW_DEBUG_OUTPUT_DIR")
        log_level: str = Field(default="INFO")


else:

    def _load_env_file() -> dict[str, str]:
        values: dict[str, str] = {}
        for raw_path in ENV_FILE_CANDIDATES:
            env_path = Path(raw_path)
            if not env_path.exists():
                continue
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    _ENV_FILE_VALUES = _load_env_file()

    def _get_env(name: str, default: str = "") -> str:
        return os.getenv(name, _ENV_FILE_VALUES.get(name, default))

    @dataclass
    class Settings:
        """Fallback settings loader when pydantic-settings is unavailable."""

        tencent_docs_token: str = _get_env("TENCENT_DOCS_TOKEN", "")
        tencent_docs_client_id: str = _get_env("TENCENT_DOCS_CLIENT_ID", "")
        tencent_docs_open_id: str = _get_env("TENCENT_DOCS_OPEN_ID", "")
        tencent_docs_base_url: str = _get_env("TENCENT_DOCS_BASE_URL", "https://docs.qq.com/openapi")

        llm_provider: str = _get_env("LLM_PROVIDER", "deepseek")
        llm_api_key: str = _get_env("LLM_API_KEY", _get_env("DEEPSEEK_API_KEY", ""))
        llm_base_url: str = _get_env("LLM_BASE_URL", _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
        llm_model: str = _get_env("LLM_MODEL", _get_env("DEEPSEEK_MODEL", "deepseek-chat"))

        deepseek_api_key: str = _get_env("DEEPSEEK_API_KEY", "")
        deepseek_base_url: str = _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        deepseek_model: str = _get_env("DEEPSEEK_MODEL", "deepseek-chat")

        minimax_api_key: str = _get_env("MINIMAX_API_KEY", "")
        minimax_base_url: str = _get_env("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
        minimax_model: str = _get_env("MINIMAX_MODEL", "MiniMax-M2.7")

        search_provider: str = _get_env("SEARCH_PROVIDER", "disabled")
        search_api_key: Optional[str] = _get_env("SEARCH_API_KEY") or None
        search_base_url: str = _get_env("SEARCH_BASE_URL", "https://api.tavily.com/search")
        search_max_results: int = int(_get_env("SEARCH_MAX_RESULTS", "5"))
        search_timeout: int = int(_get_env("SEARCH_TIMEOUT", "20"))
        search_depth: str = _get_env("SEARCH_DEPTH", "basic")
        search_topic: str = _get_env("SEARCH_TOPIC", "general")
        review_rules_template_path: str = _get_env("REVIEW_RULES_TEMPLATE_PATH", "")
        review_structure_template_path: str = _get_env("REVIEW_STRUCTURE_TEMPLATE_PATH", "")
        batch_size: int = int(_get_env("BATCH_SIZE", "5"))
        request_timeout: int = int(_get_env("REQUEST_TIMEOUT", "30"))
        tencent_docs_max_retries: int = int(_get_env("TENCENT_DOCS_MAX_RETRIES", "2"))
        tencent_docs_retry_delay: float = float(_get_env("TENCENT_DOCS_RETRY_DELAY", "1.0"))
        skill_mcp_client: str = _get_env("SKILL_MCP_CLIENT", "mock")
        mcp_bridge_timeout: int = int(_get_env("MCP_BRIDGE_TIMEOUT", "120"))
        openclaw_mcp_bridge_executable: str = _get_env("OPENCLAW_MCP_BRIDGE_EXECUTABLE", "")
        openclaw_mcp_bridge_args: str = _get_env("OPENCLAW_MCP_BRIDGE_ARGS", "")
        claude_code_mcp_bridge_executable: str = _get_env("CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE", "")
        claude_code_mcp_bridge_args: str = _get_env("CLAUDE_CODE_MCP_BRIDGE_ARGS", "")
        review_debug_output_dir: str = _get_env("REVIEW_DEBUG_OUTPUT_DIR", "")
        log_level: str = _get_env("LOG_LEVEL", "INFO")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from the environment."""
    global _settings
    _settings = Settings()
    return _settings
