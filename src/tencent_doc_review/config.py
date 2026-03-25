"""
配置管理模块
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # 腾讯文档配置
    tencent_docs_token: str = Field(
        default="",
        description="腾讯文档 MCP Token",
        alias="TENCENT_DOCS_TOKEN"
    )
    
    tencent_docs_base_url: str = Field(
        default="https://docs.qq.com/openapi/mcp",
        description="腾讯文档 MCP 基础 URL"
    )
    
    # DeepSeek 配置
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API Key",
        alias="DEEPSEEK_API_KEY"
    )
    
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API 基础 URL"
    )
    
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek 模型名称"
    )
    
    # 搜索配置（可选）
    search_api_key: Optional[str] = Field(
        default=None,
        description="搜索引擎 API Key",
        alias="SEARCH_API_KEY"
    )
    
    # 应用配置
    batch_size: int = Field(
        default=5,
        description="批量处理时的并发数"
    )
    
    request_timeout: int = Field(
        default=30,
        description="请求超时时间（秒）"
    )
    
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = Settings()
    return _settings
