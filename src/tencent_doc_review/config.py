"""Application settings."""

from __future__ import annotations

import os
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


if BaseSettings is not None:

    class Settings(BaseSettings):
        """Application settings loaded from environment variables."""

        model_config = SettingsConfigDict(
            env_file=".env",
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

        search_api_key: Optional[str] = Field(default=None, alias="SEARCH_API_KEY")
        batch_size: int = Field(default=5)
        request_timeout: int = Field(default=30)
        log_level: str = Field(default="INFO")


else:

    def _load_env_file() -> dict[str, str]:
        values: dict[str, str] = {}
        env_path = Path(".env")
        if not env_path.exists():
            return values

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

        search_api_key: Optional[str] = _get_env("SEARCH_API_KEY") or None
        batch_size: int = int(_get_env("BATCH_SIZE", "5"))
        request_timeout: int = int(_get_env("REQUEST_TIMEOUT", "30"))
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
