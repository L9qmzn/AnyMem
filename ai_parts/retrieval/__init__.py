"""
检索策略模块

提供可插拔的检索策略，支持：

基础策略:
- text: 纯文本向量检索
- image: 纯图片向量检索
- vector: 向量检索（文本+图片合并）

混合策略:
- hybrid: 混合检索（简单合并）
- rrf: RRF 倒数排名融合
- weighted: 加权融合检索

BM25 + Vector 混合:
- bm25: BM25 关键词检索
- bm25_vector: BM25 + Vector RRF 融合
- bm25_vector_alpha: BM25 + Vector Alpha 加权融合
- adaptive: 自适应混合检索（根据查询特征动态调整权重）

使用示例:
    from ai_parts.retrieval import get_retriever, list_retrievers, RetrievalQuery

    # 列出所有可用策略
    strategies = list_retrievers()

    # 获取检索器实例
    retriever = get_retriever("bm25_vector", index_manager=manager)

    # 执行检索
    results = retriever.retrieve(RetrievalQuery(query="搜索内容", top_k=10))

添加新策略:
    from ai_parts.retrieval import register, BaseRetriever

    @register("my_strategy", "我的策略描述")
    class MyRetriever(BaseRetriever):
        def retrieve(self, query):
            ...

BM25 索引初始化:
    from ai_parts.retrieval.bm25 import build_bm25_from_index_manager, set_bm25_index

    # 在应用启动时构建 BM25 索引
    bm25_index = build_bm25_from_index_manager(index_manager)
    set_bm25_index(bm25_index)
"""

from .base import BaseRetriever, RetrievalQuery, RetrievalResult
from .registry import get_retriever, get_retriever_class, has_retriever, list_retrievers, register

# 导入策略模块以触发注册
from . import vector
from . import hybrid
from . import bm25
from . import fusion

# BM25 相关导出
from .bm25 import (
    BM25Index,
    build_bm25_from_index_manager,
    get_bm25_index,
    set_bm25_index,
)

__all__ = [
    # 基类
    "BaseRetriever",
    "RetrievalQuery",
    "RetrievalResult",
    # 注册表
    "register",
    "get_retriever",
    "get_retriever_class",
    "list_retrievers",
    "has_retriever",
    # BM25
    "BM25Index",
    "build_bm25_from_index_manager",
    "get_bm25_index",
    "set_bm25_index",
]
