"""
异步标签生成服务
"""
import re
from typing import List, Dict, Any
from openai import AsyncOpenAI

from ai_parts.config import get_settings
from ai_parts.models import Attachment, Memo


settings = get_settings()

# 创建异步 OpenAI 客户端
async_client = AsyncOpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key,
)


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
    """从附件里提取图片 URL，用于给模型做视觉输入。"""
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


async def generate_tags_for_memo(
    memo: Memo,
    user_all_tags: List[str],
    max_tags: int = 5,
) -> List[str]:
    """
    异步为一条 memo 生成标签：
      - 使用 memo.content
      - 使用非图片附件信息
      - 使用图片附件 URL 做 vision 输入
    返回：只包含 AI 新建议的标签（不含 memo.tags）
    """
    content = memo.content or ""
    existing_tags = memo.tags or []
    attachments = memo.attachments or []

    reuse_candidates = sorted(set(existing_tags + (user_all_tags or [])))
    reuse_candidates_str = ", ".join(reuse_candidates) if reuse_candidates else "无"

    non_image_desc = build_non_image_attachment_description(
        attachments,
        settings.max_attachments
    )
    image_urls = extract_image_urls(attachments, settings.max_images)

    text_prompt = f"""
你是一个个人备忘录应用的「标签助手」。

现在有一条备忘录，请根据它的**正文内容**、**非图片附件信息**，以及（如果有的话）**图片内容**来生成合适的标签。

【备忘录正文】
\"\"\"{content}\"\"\"

【非图片附件列表说明】
{non_image_desc}

【用户在整个应用中常用的标签（优先复用这些）】
{reuse_candidates_str}

【这条备忘录目前已有的标签】
{", ".join(existing_tags) if existing_tags else "无"}

核心原则：
1. **具体胜过抽象** - 优先提取具体名称：
   - 宠物名（"小黑"、"旺财"）比类别（"狗"）重要
   - 产品型号（"iPhone 15"、"MacBook Pro"）比类别（"手机"）重要
   - 人名（"李总"）、公司名（"阿里"）、书名（"三体"）都要提取
   - 如果正文有"小黑#狗"，提取"小黑"，不要输出"狗"

2. **复用避免碎片** - 标签池里有就用原词：
   - 池里有"阅读"，就不要写"读书"、"看书"等变体
   - 池里有"工作"，就不要创造"工作记录"、"工作笔记"
   - 语义完全相同才复用，不同就创建新的

3. **类型化敏感信息** - 敏感内容标注类型而非具体值：
   - 银行卡 → 输出"卡号"（不输出具体卡号）
   - API密钥 → 输出"API Key"（不输出密钥本身）
   - 密码 → 输出"密码"（不输出密码内容）

4. **控制数量** - 少而精：
   - 目标 2-3 个标签，最多 {max_tags} 个
   - 宁缺毋滥，只要最关键的信息

5. **格式要求**：
   - 每个标签 1～6 个字
   - 不带 # 号和其他符号
   - 不要重复已有标签
   - 只输出标签，逗号分隔，无解释

关键：记住具体名称永远比分类更有价值！
"""

    # 使用异步 API 调用
    if image_urls:
        messages = [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": text_prompt},
                *[
                    {"type": "input_image", "image_url": url}
                    for url in image_urls
                ],
            ],
        }]
        response = await async_client.responses.create(
            model=settings.tag_generation_model,
            input=messages,
        )
    else:
        # 没有图片就简单点，直接把 prompt 当纯文本传
        response = await async_client.responses.create(
            model=settings.tag_generation_model,
            input=text_prompt,
        )

    raw_text = (response.output_text or "").strip()

    # 解析标签
    candidates = [t.strip() for t in re.split(r"[，,]", raw_text) if t.strip()]
    new_tags = [t for t in candidates if t not in existing_tags]

    # 自身去重
    seen = set()
    deduped = []
    for t in new_tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    return deduped[:max_tags]
