"""
AI服务配置管理
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """AI服务配置"""

    # OpenAI API 配置
    openai_api_base: str = ""
    openai_api_key: str = ""

    # 模型配置
    tag_generation_model: str = "gpt-4.1-mini"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8001

    # 标签生成配置
    max_tags: int = 5
    max_images: int = 3
    max_attachments: int = 5

    class Config:
        env_prefix = "AI_SERVICE_"
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
