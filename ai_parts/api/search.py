"""
搜索 API 端点
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_parts.indexing.index_manager import IndexManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/search", tags=["search"])

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

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    search_mode: str = "hybrid"  # "text", "image", "hybrid"
    min_score: float = 0.0
    creator: Optional[str] = None  # 用户过滤，格式如 "users/1"


class SearchResult(BaseModel):
    memo_uid: str
    memo_name: str  # 完整的 memo name，如 "memos/123"
    score: float
    content: str
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


# ==================== API 端点 ====================

@router.post("", response_model=SearchResponse)
async def search_memos(request: SearchRequest):
    """语义搜索Memo"""
    try:
        manager = get_index_manager()

        # 根据搜索模式选择索引
        if request.search_mode == "text":
            # 纯文本搜索
            retriever = manager.text_index.as_retriever(similarity_top_k=request.top_k)
            nodes = retriever.retrieve(request.query)
        elif request.search_mode == "image":
            # 纯图片搜索
            if manager.image_index is None:
                raise HTTPException(status_code=400, detail="Image search not available")
            retriever = manager.image_index.as_retriever(similarity_top_k=request.top_k)
            nodes = retriever.retrieve(request.query)
        else:
            # 混合搜索：分别检索文本和图片，合并结果
            text_retriever = manager.text_index.as_retriever(similarity_top_k=request.top_k)
            text_nodes = text_retriever.retrieve(request.query)

            image_nodes = []
            if manager.image_index:
                image_retriever = manager.image_index.as_retriever(similarity_top_k=request.top_k)
                image_nodes = image_retriever.retrieve(request.query)

            # 合并并按分数排序
            nodes = sorted(
                text_nodes + image_nodes,
                key=lambda n: n.score or 0.0,
                reverse=True
            )[:request.top_k]

        # 过滤低分结果并转换为响应格式
        results = []
        seen_memos = set()

        for node in nodes:
            score = node.score or 0.0
            if score < request.min_score:
                continue

            metadata = node.metadata or {}
            # memo_uid 已经是完整的 memo.name 格式，如 "memos/123"
            memo_uid = metadata.get("memo_uid", "")

            # 用户过滤：只返回属于指定用户的 memo
            if request.creator:
                node_creator = metadata.get("creator", "")
                if node_creator != request.creator:
                    continue

            # 去重：同一个memo只返回最高分的结果
            if memo_uid and memo_uid not in seen_memos:
                seen_memos.add(memo_uid)
                results.append(SearchResult(
                    memo_uid=memo_uid,
                    memo_name=memo_uid,  # memo_uid 就是 memo.name
                    score=score,
                    content=node.text or "",
                    metadata=metadata,
                ))

        return SearchResponse(
            query=request.query,
            results=results,
            total=len(results),
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
