"""
AI服务配置管理
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """AI服务配置"""

    # OpenAI API 配置
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # 阿里云通义千问 API 配置
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 模型配置
    tag_generation_model: str = "gpt-4.1-mini"
    vision_provider: str = "qwen"  # 'qwen' or 'openai'

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000

    # Memos 服务器配置
    memos_base_url: str = os.getenv("MEMOS_BASE_URL", "http://localhost:8081")
    # Session cookie for internal API calls (format: {userID}-{sessionID})
    memos_session_cookie: str = os.getenv("MEMOS_SESSION_COOKIE", "")

    # 标签生成配置
    max_tags: int = 5
    max_images: int = 3
    max_attachments: int = 5
    attachment_snippet_len: int = 200
    attachment_text_max_len: int = 4000
    image_caption_model: str = "qwen3-vl-plus"
    use_image_caption: bool = True

    # Embedding 配置（Jina）
    jina_api_key: str = os.getenv("JINA_API_KEY", "")
    jina_text_model: str = "jina-embeddings-v3"
    jina_image_model: str = "jina-embeddings-v4"

    class Config:
        env_prefix = "AI_SERVICE_"
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
