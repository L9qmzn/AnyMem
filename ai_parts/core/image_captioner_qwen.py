"""
Image caption helper using Qwen VL (阿里云通义千问视觉模型) - llama_index 实现

使用 llama_index 的 LLM 抽象实现图片描述生成。
支持同步和异步操作。
"""
import json
from functools import lru_cache
from typing import List, Optional

from llama_index.core.base.llms.types import (
    ChatMessage,
    ImageBlock,
    MessageRole,
    TextBlock,
)
from llama_index.llms.openai_like import OpenAILike
from pydantic import BaseModel, Field

from ai_parts.config import get_settings
from ai_parts.prompts import IMAGE_CAPTION_SYSTEM_PROMPT


# ==================== 数据模型 ====================

class ImageCaption(BaseModel):
    """图片描述结构化输出"""
    type_summary: str = ""
    visual_details: List[str] = Field(default_factory=list)
    ocr: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


# ==================== LLM 初始化 ====================

@lru_cache()
def get_qwen_vl_llm() -> OpenAILike:
    """获取 Qwen VL LLM 实例（单例）"""
    settings = get_settings()
    return OpenAILike(
        api_base=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
        model=settings.image_caption_model,
        is_chat_model=True,
        is_function_calling_model=False,
        timeout=120.0,  # 图片处理可能需要更长时间
    )


# ==================== 辅助函数 ====================

def _format_caption(payload: ImageCaption) -> str:
    """将结构化描述格式化为文本。"""
    def _join(items: List[str]) -> str:
        return "; ".join([v for v in items if v])

    lines = [
        f"1. 图片类型与摘要：{payload.type_summary}",
        f"2. 详细视觉内容：{_join(payload.visual_details)}",
        f"3. 文字提取 (OCR)：{_join(payload.ocr)}",
        f"4. 关键词提取：{', '.join([k for k in payload.keywords if k])}",
    ]
    return "\n".join([ln for ln in lines if ln])


def _parse_json_response(response_text: str) -> Optional[ImageCaption]:
    """
    解析 LLM 返回的 JSON 响应。
    支持纯 JSON 和 markdown 代码块包裹的 JSON。
    """
    try:
        text = response_text.strip()

        # 尝试从 markdown 代码块中提取 JSON
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        data = json.loads(text)
        return ImageCaption(
            type_summary=data.get("type_summary", ""),
            visual_details=data.get("visual_details", []),
            ocr=data.get("ocr", []),
            keywords=data.get("keywords", []),
        )
    except Exception as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response text: {response_text[:500]}")
        return None


def _build_caption_messages(
    image_url: str,
    hint: Optional[str] = None,
) -> List[ChatMessage]:
    """构建图片描述生成的消息列表。"""
    # 构建用户提示词
    user_prompt = IMAGE_CAPTION_SYSTEM_PROMPT
    if hint:
        user_prompt += f"\n参考提示: {hint}"

    # 系统消息
    system_message = ChatMessage(
        role=MessageRole.SYSTEM,
        blocks=[TextBlock(text="You are a helpful assistant.")],
    )

    # 用户消息（文本 + 图片）
    user_message = ChatMessage(
        role=MessageRole.USER,
        blocks=[
            TextBlock(text=user_prompt),
            ImageBlock(url=image_url),
        ],
    )

    return [system_message, user_message]


# ==================== 核心生成函数 ====================

def generate_caption(
    image: str,
    hint: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    同步生成图片描述。

    Args:
        image: 图片 URL 或 data URL
        hint: 可选的上下文提示
        model: 可选的模型名称覆盖

    Returns:
        格式化的描述文本，失败返回 None
    """
    settings = get_settings()

    # 检查 API key 配置
    if not settings.dashscope_api_key:
        print("Warning: DASHSCOPE_API_KEY not configured, falling back to None")
        return None

    try:
        # 获取 LLM（如果指定了不同的模型，创建新实例）
        if model and model != settings.image_caption_model:
            llm = OpenAILike(
                api_base=settings.dashscope_base_url,
                api_key=settings.dashscope_api_key,
                model=model,
                is_chat_model=True,
                timeout=120.0,
            )
        else:
            llm = get_qwen_vl_llm()

        # 构建消息
        messages = _build_caption_messages(image, hint)

        # 调用 LLM
        response = llm.chat(messages)
        response_text = response.message.content or ""

        # 解析响应
        parsed = _parse_json_response(response_text)
        if parsed:
            return _format_caption(parsed)
        else:
            print("Warning: Failed to parse structured response, returning raw text")
            return response_text

    except Exception as e:
        print(f"Error generating caption with Qwen: {e}")
        return None


async def generate_caption_async(
    image: str,
    hint: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    异步生成图片描述（用于批量处理）。

    Args:
        image: 图片 URL 或 data URL
        hint: 可选的上下文提示
        model: 可选的模型名称覆盖

    Returns:
        格式化的描述文本，失败返回 None
    """
    settings = get_settings()

    # 检查 API key 配置
    if not settings.dashscope_api_key:
        print("Warning: DASHSCOPE_API_KEY not configured, falling back to None")
        return None

    try:
        # 获取 LLM（如果指定了不同的模型，创建新实例）
        if model and model != settings.image_caption_model:
            llm = OpenAILike(
                api_base=settings.dashscope_base_url,
                api_key=settings.dashscope_api_key,
                model=model,
                is_chat_model=True,
                timeout=120.0,
            )
        else:
            llm = get_qwen_vl_llm()

        # 构建消息
        messages = _build_caption_messages(image, hint)

        # 异步调用 LLM
        response = await llm.achat(messages)
        response_text = response.message.content or ""

        # 解析响应
        parsed = _parse_json_response(response_text)
        if parsed:
            return _format_caption(parsed)
        else:
            print("Warning: Failed to parse structured response, returning raw text")
            return response_text

    except Exception as e:
        print(f"Error generating caption with Qwen: {e}")
        return None
