"""
异步标签生成服务
"""
import re
from typing import List, Dict, Any
from openai import AsyncOpenAI

from config import get_settings
from models import Memo, Attachment


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
        att_content = att.content or ""

        att_content_snippet = ""
        if att_content:
            snippet = att_content.strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            att_content_snippet = f"，部分内容预览：{snippet}"

        line = f"{count}) 类型: {att_type}，文件名: {filename}{att_content_snippet}"
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

        url = att.externalLink or att.content or ""
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

要求：
1. 结合正文 + 附件 + 图片的主题来思考，标签可以反映：
   - 内容主题（如：哲学、论文、工作、旅游、宠物）
   - 文档或媒体类型（如：论文、截图、合约、照片）
   - 重要实体（如：柏拉图、公司名称、项目名、地点）
2. 尽量复用给出的"常用标签"，如果语义接近就直接用已有的标签名。
3. 每个标签 1～6 个字，必须是**中文或中英文混合**，不要带 # 号。
4. 不要生成和当前 memo 已有标签完全重复的标签。
5. 最多生成 {max_tags} 个标签。
6. 只输出标签本身，用中文或英文逗号分隔，不要任何解释性文字。

输出示例（仅示意）：
论文, 哲学, 柏拉图
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
