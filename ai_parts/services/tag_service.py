"""
异步标签生成服务 - 基于 llama_index 生态

使用 llama_index 的 LLM 抽象和 PromptTemplate 实现标签生成。
支持纯文本和多模态（带图片）两种场景。
"""
import re
from functools import lru_cache
from typing import List, Sequence

from llama_index.core.base.llms.types import (
    ChatMessage,
    ContentBlock,
    ImageBlock,
    MessageRole,
    TextBlock,
)
from llama_index.llms.openai_like import OpenAILike
from pydantic import BaseModel, Field

from ai_parts.config import get_settings
from ai_parts.models import Attachment, Memo
from ai_parts.prompts import TAG_GENERATION_TEMPLATE


# ==================== Pydantic 输出模型 ====================

class TagGenerationOutput(BaseModel):
    """标签生成结构化输出"""
    tags: List[str] = Field(
        default_factory=list,
        description="生成的标签列表，每个标签1-6个字，不带#号"
    )


# ==================== LLM 初始化 ====================

@lru_cache()
def get_llm() -> OpenAILike:
    """获取 LLM 实例（单例），同时支持纯文本和多模态"""
    settings = get_settings()
    return OpenAILike(
        api_base=settings.openai_api_base,
        api_key=settings.openai_api_key,
        model=settings.tag_generation_model,
        is_chat_model=True,
        is_function_calling_model=False,
        timeout=60.0,
    )


# ==================== 辅助函数 ====================

def build_non_image_attachment_description(
    attachments: List[Attachment],
    max_attachments: int = 5
) -> str:
    """把非图片附件列表转成一段给模型看的描述文本。"""
    if not attachments:
        return "无"

    lines = []
    count = 0
    for att in attachments:
        att_type = (att.type or "unknown").lower()
        if att_type.startswith("image/"):
            continue

        count += 1
        if count > max_attachments:
            break

        filename = att.filename or "unknown"
        line = f"{count}) 类型: {att_type}，文件名: {filename}"
        lines.append(line)

    return "\n".join(lines) if lines else "无"


def extract_image_urls(
    attachments: List[Attachment],
    max_images: int = 3
) -> List[str]:
    """从附件里提取图片 URL 列表。"""
    image_urls = []
    for att in attachments:
        att_type = (att.type or "").lower()
        if not att_type.startswith("image/"):
            continue

        url = att.externalLink or ""
        if not url:
            continue

        image_urls.append(url)
        if len(image_urls) >= max_images:
            break

    return image_urls


def build_multimodal_content(
    text: str,
    image_urls: List[str],
) -> Sequence[ContentBlock]:
    """构建多模态消息内容（文本 + 图片），使用 llama_index 的 Block 类型。"""
    blocks: List[ContentBlock] = [TextBlock(text=text)]
    for url in image_urls:
        blocks.append(ImageBlock(url=url))
    return blocks


def parse_tags_from_response(raw_text: str, existing_tags: List[str], max_tags: int) -> List[str]:
    """从 LLM 响应文本中解析标签列表。"""
    # 解析标签（支持中英文逗号分隔）
    candidates = [t.strip() for t in re.split(r"[，,]", raw_text) if t.strip()]

    # 过滤已存在的标签
    new_tags = [t for t in candidates if t not in existing_tags]

    # 去重并保持顺序
    seen = set()
    deduped = []
    for t in new_tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    return deduped[:max_tags]


# ==================== 核心生成函数 ====================

async def generate_tags_for_memo(
    memo: Memo,
    user_all_tags: List[str],
    max_tags: int = 5,
) -> List[str]:
    """
    异步为一条 memo 生成标签（llama_index 实现）。

    Args:
        memo: 备忘录对象
        user_all_tags: 用户所有常用标签
        max_tags: 最多生成的标签数量

    Returns:
        只包含 AI 新建议的标签（不含 memo.tags）
    """
    settings = get_settings()

    content = memo.content or ""
    existing_tags = memo.tags or []
    attachments = memo.attachments or []

    # 准备 prompt 变量
    reuse_candidates = sorted(set(existing_tags + (user_all_tags or [])))
    reuse_candidates_str = ", ".join(reuse_candidates) if reuse_candidates else "无"

    non_image_desc = build_non_image_attachment_description(
        attachments,
        settings.max_attachments
    )

    # 格式化 prompt
    prompt_text = TAG_GENERATION_TEMPLATE.format(
        content=content,
        non_image_desc=non_image_desc,
        reuse_candidates=reuse_candidates_str,
        existing_tags=", ".join(existing_tags) if existing_tags else "无",
        max_tags=max_tags,
    )

    # 提取图片 URL
    image_urls = extract_image_urls(attachments, settings.max_images)

    # 获取 LLM 实例
    llm = get_llm()

    # 根据是否有图片构造不同的消息
    if image_urls:
        # 多模态：使用 ChatMessage 携带图片（用 blocks 参数）
        message = ChatMessage(
            role=MessageRole.USER,
            blocks=build_multimodal_content(prompt_text, image_urls),
        )
        response = await llm.achat([message])
        raw_text = response.message.content
    else:
        # 纯文本：直接调用 acomplete
        response = await llm.acomplete(prompt_text)
        raw_text = response.text

    raw_text = (raw_text or "").strip()

    # 解析并返回标签
    return parse_tags_from_response(raw_text, existing_tags, max_tags)
