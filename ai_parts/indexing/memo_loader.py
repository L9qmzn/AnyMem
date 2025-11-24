"""
将 Memo 转成 LlamaIndex 可用的多模态 Document 结构.
"""
import base64
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from urllib.parse import quote

import httpx
from llama_index.core.schema import Document, ImageDocument

from ai_parts.config import Settings, get_settings
from ai_parts.models import Attachment, Memo

logger = logging.getLogger(__name__)


@dataclass
class MemoMultimodalDocs:
    base_doc: Document
    image_docs: List[ImageDocument] = field(default_factory=list)
    attachment_docs: List[Document] = field(default_factory=list)


def _is_image(att: Attachment) -> bool:
    mime = (getattr(att, "type", "") or "").lower()
    return mime.startswith("image/")


def _is_text_like(att: Attachment) -> bool:
    mime = (getattr(att, "type", "") or "").lower()
    return mime.startswith("text/") or mime in {"text/markdown", "application/markdown"}


def _maybe_decode_text(raw: str) -> Optional[str]:
    if not raw:
        return None

    data_part = raw
    if raw.startswith("data:") and "," in raw:
        data_part = raw.split(",", 1)[1]

    try:
        decoded = base64.b64decode(data_part, validate=False).decode("utf-8", errors="replace").strip()
        if decoded:
            return decoded
    except Exception:
        pass

    if raw.startswith("data:"):
        return None

    return raw.strip() or None


def _attachment_text(att: Attachment, max_len: int) -> Optional[str]:
    raw = getattr(att, "content", None) or ""
    text = _maybe_decode_text(raw)
    if not text:
        return None
    if max_len and len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _attachment_preview(att: Attachment, max_len: int) -> str:
    text = _attachment_text(att, max_len)
    if not text:
        return ""
    compact = text.replace("\n", " ").strip()
    if len(compact) > max_len:
        return compact[:max_len] + "..."
    return compact


def _fetch_image_from_url(url: str, mime_type: str = "image/jpeg", session_cookie: str = "") -> Optional[str]:
    """从 URL 获取图片并转换为 data URL"""
    try:
        cookies = {}
        if session_cookie:
            cookies["user_session"] = session_cookie
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, cookies=cookies)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", mime_type).split(";")[0]
            b64_content = base64.b64encode(content).decode("utf-8")
            return f"data:{content_type};base64,{b64_content}"
    except Exception as e:
        logger.warning(f"Failed to fetch image from {url}: {e}")
        return None


def _build_data_url(att: Attachment, settings: Optional[Settings] = None) -> Optional[str]:
    """构建图片的 data URL。优先级：externalLink > content > memos 服务器 URL"""
    if getattr(att, "externalLink", None):
        return att.externalLink

    content = getattr(att, "content", None)
    if content:
        if isinstance(content, bytes):
            content = base64.b64encode(content).decode("utf-8")
        if str(content).startswith("data:"):
            return str(content)
        mime = getattr(att, "type", None) or "application/octet-stream"
        return f"data:{mime};base64,{content}"

    # 如果没有 externalLink 和 content，尝试从 memos 服务器获取
    cfg = settings or get_settings()
    memos_base_url = getattr(cfg, "memos_base_url", None)
    memos_session_cookie = getattr(cfg, "memos_session_cookie", "") or ""
    att_name = getattr(att, "name", None)  # e.g., "attachments/{uid}"
    filename = getattr(att, "filename", None)

    if memos_base_url and att_name and filename:
        # URL 格式: {memos_base_url}/file/{att_name}/{filename}
        url = f"{memos_base_url}/file/{att_name}/{quote(filename)}"
        mime = getattr(att, "type", None) or "image/jpeg"
        logger.info(f"Fetching image from memos server: {url}")
        return _fetch_image_from_url(url, mime, memos_session_cookie)

    return None


def _build_attachment_block(
    attachments: List[Attachment],
    max_attachments: int,
    snippet_len: int,
) -> str:
    lines = []
    count = 0
    for att in attachments:
        if _is_image(att):
            continue
        count += 1
        if max_attachments and count > max_attachments:
            break

        att_type = (getattr(att, "type", "") or "unknown").lower()
        filename = getattr(att, "filename", None) or getattr(att, "name", None) or "unknown"
        preview = _attachment_preview(att, snippet_len)

        line = f"{count}) type: {att_type}, filename: {filename}"
        if preview:
            line = f"{line}, preview: {preview}"
        lines.append(line)
    return "\n".join(lines)


def _build_metadata(memo: Memo, attachments_len: int) -> dict:
    properties = getattr(memo, "property", None)
    if properties is not None and hasattr(properties, "model_dump"):
        properties = properties.model_dump()
    if isinstance(properties, dict):
        properties = ", ".join([f"{k}={v}" for k, v in properties.items()])

    ai_tags = getattr(memo, "aiTags", []) or []
    if isinstance(ai_tags, list):
        ai_tags = ", ".join([str(t) for t in ai_tags if t])

    metadata = {
        "memo_uid": getattr(memo, "name", None),
        "memo_id": getattr(memo, "id", None),
        "creator": getattr(memo, "creator", None),
        "created_at": getattr(memo, "createTime", None),
        "updated_at": getattr(memo, "updateTime", None),
        "display_time": getattr(memo, "displayTime", None),
        "visibility": getattr(memo, "visibility", None),
        "pinned": getattr(memo, "pinned", False),
        "tags": ", ".join([str(t) for t in getattr(memo, "tags", []) or []]),
        "ai_tags": ai_tags,
        "properties": properties,
        "attachment_count": attachments_len,
        "source": "memo",
    }
    return {k: v for k, v in metadata.items() if v not in (None, [], {})}


def load_memo_to_llama_docs(
    memo: Memo,
    settings: Optional[Settings] = None,
    attachment_snippet_length: Optional[int] = None,
    image_caption_fn: Optional[Callable[[str, dict], Optional[str]]] = None,
) -> MemoMultimodalDocs:
    cfg = settings or get_settings()
    max_imgs = getattr(cfg, "max_images", 0)
    max_atts = getattr(cfg, "max_attachments", 0)
    snippet_len = attachment_snippet_length or getattr(cfg, "attachment_snippet_len", 200)
    text_cap = getattr(cfg, "attachment_text_max_len", 4000)

    attachments = getattr(memo, "attachments", None) or []
    content = (getattr(memo, "content", None) or "").strip()
    attachment_block = _build_attachment_block(attachments, max_atts, snippet_len)

    base_text = content
    if attachment_block:
        base_text = f"{content}\n\n[Attachments]\n{attachment_block}"

    base_doc = Document(
        text=base_text,
        doc_id=f"memo:{getattr(memo, 'name', None) or getattr(memo, 'id', '')}",
        metadata=_build_metadata(memo, len(attachments)),
    )

    image_docs: List[ImageDocument] = []
    for idx, att in enumerate(attachments):
        if not _is_image(att):
            continue
        if max_imgs and len(image_docs) >= max_imgs:
            break

        image_payload = _build_data_url(att, cfg)
        if not image_payload:
            logger.warning(f"Cannot get image data for attachment: {getattr(att, 'name', 'unknown')}")
            continue

        caption = getattr(att, "filename", None) or getattr(att, "name", None) or ""
        if image_caption_fn:
            meta = {
                "memo_uid": getattr(memo, "name", None),
                "attachment_uid": getattr(att, "name", None),
                "filename": getattr(att, "filename", None),
                "type": getattr(att, "type", None),
            }
            custom_caption = image_caption_fn(image_payload, meta) or None
            if custom_caption:
                caption = custom_caption

        image_docs.append(
            ImageDocument(
                image=image_payload,
                text=caption,
                doc_id=f"memo:{getattr(memo, 'name', None)}:img:{idx}",
                metadata={
                    "memo_uid": getattr(memo, "name", None),
                    "creator": getattr(memo, "creator", None),  # 用户过滤用
                    "attachment_uid": getattr(att, "name", None),
                    "filename": getattr(att, "filename", None),
                    "type": getattr(att, "type", None),
                },
            )
        )

    attachment_docs: List[Document] = []
    for idx, att in enumerate(attachments):
        if not _is_text_like(att):
            continue

        text = _attachment_text(att, text_cap)
        if not text:
            continue

        attachment_docs.append(
            Document(
                text=text,
                doc_id=f"memo:{getattr(memo, 'name', None)}:att:{idx}",
                metadata={
                    "memo_uid": getattr(memo, "name", None),
                    "creator": getattr(memo, "creator", None),  # 用户过滤用
                    "attachment_uid": getattr(att, "name", None),
                    "filename": getattr(att, "filename", None),
                    "type": getattr(att, "type", None),
                    "source": "memo_attachment",
                },
            )
        )

    return MemoMultimodalDocs(
        base_doc=base_doc,
        image_docs=image_docs,
        attachment_docs=attachment_docs,
    )
