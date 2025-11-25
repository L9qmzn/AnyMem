"""
索引管理 API 端点
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ai_parts.config import get_settings
from ai_parts.core.image_captioner_qwen import generate_caption_async
from ai_parts.indexing.index_manager import IndexManager
from ai_parts.indexing.memo_loader import MemoMultimodalDocs, load_memo_to_llama_docs
from ai_parts.models import Memo

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/internal/index", tags=["indexing"])

# 全局索引管理器引用（由主应用注入）
_index_manager: Optional[IndexManager] = None


def set_index_manager(manager: IndexManager):
    """设置全局索引管理器"""
    global _index_manager
    _index_manager = manager


def get_index_manager() -> IndexManager:
    """获取索引管理器"""
    if _index_manager is None:
        raise RuntimeError("Index manager not initialized")
    return _index_manager


# ==================== 请求/响应模型 ====================

class IndexMemoRequest(BaseModel):
    memo: dict
    operation: str = "upsert"


class IndexMemoResponse(BaseModel):
    memo_uid: str
    status: str
    text_vectors: Optional[int] = None
    image_vectors: Optional[int] = None
    timestamp: str


class DeleteMemoResponse(BaseModel):
    memo_uid: str
    deleted: bool
    text_vectors_removed: int
    image_vectors_removed: int


class IndexStatusResponse(BaseModel):
    total_memos: int
    total_text_vectors: int
    total_image_vectors: int
    collections: dict
    persist_dirs: dict


class RebuildIndexRequest(BaseModel):
    creator: str  # 用户标识，如 "users/1"


class RebuildIndexResponse(BaseModel):
    creator: str
    status: str
    total_memos: int
    timestamp: str


# 重建任务状态追踪
_rebuild_tasks: Dict[str, dict] = {}


def get_rebuild_status(creator: str) -> Optional[dict]:
    """获取重建任务状态"""
    return _rebuild_tasks.get(creator)


# ==================== 辅助函数 ====================

async def fetch_user_memos(creator: str) -> List[dict]:
    """从 memos 服务器获取用户的所有 memo"""
    memos_base_url = settings.memos_base_url
    session_cookie = settings.memos_session_cookie

    all_memos = []
    page_token = ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            url = f"{memos_base_url}/api/v1/memos"
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token

            cookies = {}
            if session_cookie:
                cookies["user_session"] = session_cookie

            response = await client.get(url, params=params, cookies=cookies)
            response.raise_for_status()
            data = response.json()

            memos = data.get("memos", [])
            # 按 creator 过滤
            for memo in memos:
                if memo.get("creator") == creator:
                    all_memos.append(memo)

            page_token = data.get("nextPageToken", "")
            if not page_token:
                break

    return all_memos


async def process_rebuild_index(creator: str):
    """后台任务：重建用户的所有索引"""
    task_status = _rebuild_tasks.get(creator, {})
    task_status.update({
        "status": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "completed": 0,
        "failed": 0,
        "total": 0,
    })
    _rebuild_tasks[creator] = task_status

    try:
        logger.info(f"[Rebuild] Fetching memos for {creator}")
        memos = await fetch_user_memos(creator)
        task_status["total"] = len(memos)
        logger.info(f"[Rebuild] Found {len(memos)} memos for {creator}")

        for i, memo_dict in enumerate(memos):
            try:
                memo_uid = memo_dict.get("name", "unknown")
                logger.info(f"[Rebuild] [{i+1}/{len(memos)}] Processing: {memo_uid}")

                await process_index_memo(memo_dict)
                task_status["completed"] += 1

            except Exception as e:
                logger.error(f"[Rebuild] Failed to index memo: {e}")
                task_status["failed"] += 1

        task_status["status"] = "completed"
        task_status["finished_at"] = datetime.utcnow().isoformat() + "Z"
        logger.info(f"[Rebuild] Completed for {creator}: {task_status['completed']}/{task_status['total']} memos indexed")

    except Exception as e:
        logger.error(f"[Rebuild] Failed: {e}", exc_info=True)
        task_status["status"] = "failed"
        task_status["error"] = str(e)


async def load_memo_with_async_captions(memo: Memo) -> MemoMultimodalDocs:
    """加载Memo并异步生成图片描述"""
    attachments = getattr(memo, "attachments", None) or []

    image_tasks = []
    image_indices = []

    for idx, att in enumerate(attachments):
        att_type = (getattr(att, "type", "") or "").lower()
        if not att_type.startswith("image/"):
            continue

        # 构建图片payload
        if getattr(att, "externalLink", None):
            image_payload = att.externalLink
        elif getattr(att, "content", None):
            import base64
            content = att.content
            if isinstance(content, bytes):
                content = base64.b64encode(content).decode("utf-8")
            if not str(content).startswith("data:"):
                mime = att_type or "application/octet-stream"
                image_payload = f"data:{mime};base64,{content}"
            else:
                image_payload = str(content)
        else:
            continue

        hint = getattr(att, "filename", None) or getattr(att, "name", None)
        image_tasks.append(generate_caption_async(image_payload, hint=hint))
        image_indices.append(idx)

    # 并发生成所有图片描述
    caption_map = {}
    if image_tasks:
        captions = await asyncio.gather(*image_tasks)
        for idx, caption in zip(image_indices, captions):
            if caption:
                caption_map[idx] = caption

    def _caption_fn(image_payload: str, meta: dict) -> Optional[str]:
        att_uid = meta.get("attachment_uid")
        for idx, att in enumerate(attachments):
            if getattr(att, "name", None) == att_uid:
                return caption_map.get(idx, meta.get("filename", ""))
        return meta.get("filename", "")

    if caption_map:
        return load_memo_to_llama_docs(memo, image_caption_fn=_caption_fn, settings=settings)
    else:
        return load_memo_to_llama_docs(memo, image_caption_fn=None, settings=settings)


async def process_index_memo(memo_dict: dict):
    """后台任务：索引Memo"""
    try:
        memo = Memo.model_validate(memo_dict)
        memo_uid = memo.name

        logger.info(f"[Index] Processing: {memo_uid}")
        start_time = time.time()

        docs = await load_memo_with_async_captions(memo)
        manager = get_index_manager()
        text_count, image_count = manager.add_or_update_memo(docs)

        elapsed = time.time() - start_time
        logger.info(f"[Index] Completed {memo_uid}: text={text_count}, image={image_count}, time={elapsed:.2f}s")

    except Exception as e:
        logger.error(f"[Index] Failed: {e}", exc_info=True)


# ==================== API 端点 ====================

@router.get("/status", response_model=IndexStatusResponse)
async def get_index_status():
    """获取索引状态"""
    manager = get_index_manager()
    status_info = manager.get_index_status()

    return IndexStatusResponse(
        total_memos=status_info["total_memos"],
        total_text_vectors=status_info["total_text_vectors"],
        total_image_vectors=status_info["total_image_vectors"],
        collections=status_info["collections"],
        persist_dirs=status_info["persist_dirs"],
    )


@router.post("/memo", status_code=202, response_model=IndexMemoResponse)
async def index_memo(
    request: IndexMemoRequest,
    background_tasks: BackgroundTasks,
):
    """索引或更新Memo（异步处理）"""
    memo_uid = request.memo.get("name", "unknown")
    background_tasks.add_task(process_index_memo, request.memo)

    return IndexMemoResponse(
        memo_uid=memo_uid,
        status="accepted",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.delete("/memo/{memo_uid:path}", response_model=DeleteMemoResponse)
async def delete_memo_index(memo_uid: str):
    """删除Memo的索引"""
    try:
        manager = get_index_manager()
        text_deleted, image_deleted = manager.delete_memo(memo_uid)

        return DeleteMemoResponse(
            memo_uid=memo_uid,
            deleted=text_deleted > 0 or image_deleted > 0,
            text_vectors_removed=text_deleted,
            image_vectors_removed=image_deleted,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memo/{memo_uid:path}")
async def get_memo_index_info(memo_uid: str, include_detail: bool = False):
    """获取Memo的索引信息

    Args:
        memo_uid: Memo UID
        include_detail: 是否包含详细信息（文本内容、图片描述等）
    """
    manager = get_index_manager()
    info = manager.get_memo_info(memo_uid, include_detail=include_detail)

    if info is None:
        raise HTTPException(status_code=404, detail=f"Memo {memo_uid} not indexed")

    return info


@router.post("/rebuild", status_code=202, response_model=RebuildIndexResponse)
async def rebuild_user_index(
    request: RebuildIndexRequest,
    background_tasks: BackgroundTasks,
):
    """重建用户的所有索引（异步处理）

    从 memos 服务器获取该用户的所有 memo 并重新建立索引。
    这是一个长时间运行的任务，会在后台执行。
    """
    creator = request.creator

    # 检查是否有正在运行的任务
    existing_task = get_rebuild_status(creator)
    if existing_task and existing_task.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Rebuild task for {creator} is already running"
        )

    # 启动后台任务
    background_tasks.add_task(process_rebuild_index, creator)

    return RebuildIndexResponse(
        creator=creator,
        status="accepted",
        total_memos=0,  # 实际数量会在后台任务中更新
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@router.get("/rebuild/{creator:path}")
async def get_rebuild_task_status(creator: str):
    """获取重建任务状态"""
    status = get_rebuild_status(creator)
    if status is None:
        raise HTTPException(status_code=404, detail=f"No rebuild task found for {creator}")
    return status
