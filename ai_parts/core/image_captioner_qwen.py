"""
Image caption helper using Qwen VL (阿里云通义千问视觉模型)
Provides the same interface as image_captioner.py but uses Qwen instead of OpenAI.
Supports both sync and async operations for batch processing.
"""
from typing import List, Optional
import json

from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel, Field

from ai_parts.config import get_settings


class ImageCaption(BaseModel):
    type_summary: str = ""
    visual_details: List[str] = Field(default_factory=list)
    ocr: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


def _format_caption(payload: ImageCaption) -> str:
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
    Parse JSON response from Qwen model and convert to ImageCaption.
    Handles both strict JSON and markdown-wrapped JSON.
    """
    try:
        # Try to extract JSON from markdown code blocks
        text = response_text.strip()
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


def generate_caption(
    image: str,
    hint: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a detailed caption for an image (URL or data URL) using Qwen VL.

    Args:
        image: Image URL or data URL
        hint: Optional hint/context about the image
        model: Optional model name override (default: qwen-vl-max)

    Returns:
        Formatted caption string or None if failed
    """
    settings = get_settings()

    # Check if DASHSCOPE API key is configured
    if not settings.dashscope_api_key:
        print("Warning: DASHSCOPE_API_KEY not configured, falling back to None")
        return None

    client = OpenAI(
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )

    # Use configured model or default to qwen-vl-max
    model_name = model or getattr(settings, "image_caption_model", "qwen3-vl-plus")

    system_prompt = (
        "Role: 你是一个专业的数字资产归档专家。你的任务是将图片转化为详细的文本描述，以便用于语义检索（RAG）和构建知识库索引。\n"
        "Task: 请分析这张图片，并严格按照以下四个维度生成描述：\n"
        "1. 图片类型与摘要：用一句话概括这是什么（例如：Excel表格截图、Python代码片段、手写白板笔记、风景照、网页截图等）。\n"
        "2. 详细视觉内容：\n"
        "   - 如果是图表：说明图表类型（柱状、折线等），读取横纵坐标含义，提取关键数值、最大值/最小值以及数据趋势。\n"
        "   - 如果是界面/网页：描述主要的功能区、按钮名称、选中的选项。\n"
        "   - 如果是物体/场景：描述主体对象、颜色、环境以及具体的动作。\n"
        "3. 文字提取 (OCR)：提取图片中所有可见的文字内容。如果是代码，请保留关键函数名和逻辑；如果是文档，请概括核心段落。尽量保留原文专有名词（如 Gemini 3 Pro, CUDA Error 等）。\n"
        "4. 关键词提取：列出 5-10 个最能代表图片内容的关键词（实体名、技术术语、场景标签）。\n\n"
        "Constraints:\n"
        ' - 不要输出"这张图片展示了..."，直接陈述事实。\n'
        " - 如果文字过多，提取核心要点即可，不逐字抄录，但关键数据不能错。\n"
        " - 输出语言：中文（如果图片内容主要为英文，请保留英文原文术语）。\n"
        "请按照以下JSON格式输出：\n"
        '{\n'
        '  "type_summary": "图片类型与摘要",\n'
        '  "visual_details": ["详细视觉内容1", "详细视觉内容2"],\n'
        '  "ocr": ["提取的文字1", "提取的文字2"],\n'
        '  "keywords": ["关键词1", "关键词2", "关键词3"]\n'
        '}'
    )

    if hint:
        system_prompt += f"\n参考提示: {hint}"

    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": system_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": image},
                },
            ],
        },
    ]

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},  # Ensure JSON output
            extra_body={"enable_thinking": False},
        )
        response_text = completion.choices[0].message.content

        # Try to parse JSON response
        parsed = _parse_json_response(response_text)
        if parsed:
            return _format_caption(parsed)
        else:
            # If JSON parsing failed, return raw response
            print("Warning: Failed to parse structured response, returning raw text")
            return response_text

    except Exception as e:
        # Fallback to None to avoid blocking the pipeline.
        print(f"Error generating caption with Qwen: {e}")
        return None


async def generate_caption_async(
    image: str,
    hint: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Async version of generate_caption for batch processing.

    Generate a detailed caption for an image (URL or data URL) using Qwen VL.

    Args:
        image: Image URL or data URL
        hint: Optional hint/context about the image
        model: Optional model name override (default: qwen-vl-max)

    Returns:
        Formatted caption string or None if failed
    """
    settings = get_settings()

    # Check if DASHSCOPE API key is configured
    if not settings.dashscope_api_key:
        print("Warning: DASHSCOPE_API_KEY not configured, falling back to None")
        return None

    client = AsyncOpenAI(
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )

    # Use configured model or default to qwen-vl-max
    model_name = model or getattr(settings, "image_caption_model", "qwen3-vl-plus")

    system_prompt = (
        "Role: 你是一个专业的数字资产归档专家。你的任务是将图片转化为详细的文本描述，以便用于语义检索（RAG）和构建知识库索引。\n"
        "Task: 请分析这张图片，并严格按照以下四个维度生成描述：\n"
        "1. 图片类型与摘要：用一句话概括这是什么（例如：Excel表格截图、Python代码片段、手写白板笔记、风景照、网页截图等）。\n"
        "2. 详细视觉内容：\n"
        "   - 如果是图表：说明图表类型（柱状、折线等），读取横纵坐标含义，提取关键数值、最大值/最小值以及数据趋势。\n"
        "   - 如果是界面/网页：描述主要的功能区、按钮名称、选中的选项。\n"
        "   - 如果是物体/场景：描述主体对象、颜色、环境以及具体的动作。\n"
        "3. 文字提取 (OCR)：提取图片中所有可见的文字内容。如果是代码，请保留关键函数名和逻辑；如果是文档，请概括核心段落。尽量保留原文专有名词（如 Gemini 3 Pro, CUDA Error 等）。\n"
        "4. 关键词提取：列出 5-10 个最能代表图片内容的关键词（实体名、技术术语、场景标签）。\n\n"
        "Constraints:\n"
        ' - 不要输出"这张图片展示了..."，直接陈述事实。\n'
        " - 如果文字过多，提取核心要点即可，不逐字抄录，但关键数据不能错。\n"
        " - 输出语言：中文（如果图片内容主要为英文，请保留英文原文术语）。\n"
        "请按照以下JSON格式输出：\n"
        '{\n'
        '  "type_summary": "图片类型与摘要",\n'
        '  "visual_details": ["详细视觉内容1", "详细视觉内容2"],\n'
        '  "ocr": ["提取的文字1", "提取的文字2"],\n'
        '  "keywords": ["关键词1", "关键词2", "关键词3"]\n'
        '}'
    )

    if hint:
        system_prompt += f"\n参考提示: {hint}"

    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}],
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": system_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": image},
                },
            ],
        },
    ]

    try:
        completion = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},  # Ensure JSON output
            extra_body={"enable_thinking": False},
        )
        response_text = completion.choices[0].message.content

        # Try to parse JSON response
        parsed = _parse_json_response(response_text)
        if parsed:
            return _format_caption(parsed)
        else:
            # If JSON parsing failed, return raw response
            print("Warning: Failed to parse structured response, returning raw text")
            return response_text

    except Exception as e:
        # Fallback to None to avoid blocking the pipeline.
        print(f"Error generating caption with Qwen: {e}")
        return None
