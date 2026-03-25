"""Application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
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

    @dataclass
    class Settings:
        """Fallback settings loader when pydantic-settings is unavailable."""

        tencent_docs_token: str = os.getenv("TENCENT_DOCS_TOKEN", "")
        tencent_docs_client_id: str = os.getenv("TENCENT_DOCS_CLIENT_ID", "")
        tencent_docs_open_id: str = os.getenv("TENCENT_DOCS_OPEN_ID", "")
        tencent_docs_base_url: str = os.getenv("TENCENT_DOCS_BASE_URL", "https://docs.qq.com/openapi")

        llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek")
        llm_api_key: str = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
        llm_base_url: str = os.getenv(
            "LLM_BASE_URL",
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )
        llm_model: str = os.getenv("LLM_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))

        deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        search_api_key: Optional[str] = os.getenv("SEARCH_API_KEY")
        batch_size: int = int(os.getenv("BATCH_SIZE", "5"))
        request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
        log_level: str = os.getenv("LOG_LEVEL", "INFO")


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
