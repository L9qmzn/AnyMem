"""
搜索 API 端点

使用可插拔的检索策略架构，支持多种检索方式。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_parts.indexing.index_manager import IndexManager
from ai_parts.retrieval import (
    RetrievalQuery,
    get_retriever,
    list_retrievers,
    has_retriever,
)

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
    query: str = Field(description="搜索查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    search_mode: str = Field(
        default="hybrid",
        description=(
            "检索策略: text, image, vector, hybrid, rrf, weighted, "
            "bm25, bm25_vector, bm25_vector_alpha, adaptive"
        ),
    )
    min_score: float = Field(default=0.0, ge=0.0, description="最低分数阈值")
    creator: Optional[str] = Field(
        default=None,
        description="用户过滤，格式如 users/1",
    )
    # 策略特定参数
    rrf_k: int = Field(default=60, description="RRF 常数 k（rrf, bm25_vector 策略）")
    text_weight: float = Field(default=0.7, description="文本权重（weighted 策略）")
    image_weight: float = Field(default=0.3, description="图片权重（weighted 策略）")
    # BM25 + Vector 混合参数
    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="向量权重 alpha（bm25_vector_alpha, adaptive 策略）: 0=纯BM25, 1=纯向量",
    )
    bm25_weight: float = Field(default=1.0, description="BM25 权重（bm25_vector 策略）")
    vector_weight: float = Field(default=1.0, description="向量权重（bm25_vector 策略）")


class SearchResult(BaseModel):
    memo_uid: str
    memo_name: str  # 完整的 memo name，如 "memos/123"
    score: float
    content: str
    metadata: dict
    source: str = Field(default="text", description="来源: text/image")


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: List[SearchResult]
    total: int


class RetrieverInfo(BaseModel):
    name: str
    description: str


class ListRetrieversResponse(BaseModel):
    retrievers: List[RetrieverInfo]


# ==================== API 端点 ====================


@router.get("/retrievers", response_model=ListRetrieversResponse)
async def get_available_retrievers():
    """列出所有可用的检索策略"""
    retrievers = list_retrievers()
    return ListRetrieversResponse(
        retrievers=[RetrieverInfo(**r) for r in retrievers]
    )


@router.post("", response_model=SearchResponse)
async def search_memos(request: SearchRequest):
    """
    语义搜索 Memo

    支持的检索策略:

    基础策略:
    - text: 纯文本向量检索
    - image: 纯图片向量检索
    - vector: 向量检索（文本+图片合并）

    混合策略:
    - hybrid: 混合检索（简单合并，原有默认行为）
    - rrf: RRF 倒数排名融合
    - weighted: 加权融合检索

    BM25 + Vector 混合（推荐）:
    - bm25: BM25 关键词检索
    - bm25_vector: BM25 + Vector RRF 融合
    - bm25_vector_alpha: BM25 + Vector Alpha 加权融合
    - adaptive: 自适应混合检索（根据查询特征动态调整权重）
    """
    try:
        manager = get_index_manager()

        # 检查策略是否存在
        if not has_retriever(request.search_mode):
            available = [r["name"] for r in list_retrievers()]
            raise HTTPException(
                status_code=400,
                detail=f"Unknown search_mode: '{request.search_mode}'. Available: {available}",
            )

        # 构建策略特定参数
        retriever_kwargs = {"index_manager": manager}

        if request.search_mode == "rrf":
            retriever_kwargs["k"] = request.rrf_k
        elif request.search_mode == "weighted":
            retriever_kwargs["text_weight"] = request.text_weight
            retriever_kwargs["image_weight"] = request.image_weight
        elif request.search_mode == "bm25_vector":
            retriever_kwargs["rrf_k"] = request.rrf_k
            retriever_kwargs["bm25_weight"] = request.bm25_weight
            retriever_kwargs["vector_weight"] = request.vector_weight
        elif request.search_mode == "bm25_vector_alpha":
            retriever_kwargs["alpha"] = request.alpha
        elif request.search_mode == "adaptive":
            retriever_kwargs["base_alpha"] = request.alpha

        # 获取检索器
        retriever = get_retriever(request.search_mode, **retriever_kwargs)

        # 构建查询
        filters = None
        if request.creator:
            filters = {"creator": request.creator}

        query = RetrievalQuery(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            filters=filters,
        )

        # 执行检索
        retrieval_results = retriever.retrieve(query)

        # 转换为响应格式
        results = [
            SearchResult(
                memo_uid=r.memo_uid,
                memo_name=r.memo_uid,
                score=r.score,
                content=r.content,
                metadata=r.metadata,
                source=r.source,
            )
            for r in retrieval_results
        ]

        return SearchResponse(
            query=request.query,
            search_mode=request.search_mode,
            results=results,
            total=len(results),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
