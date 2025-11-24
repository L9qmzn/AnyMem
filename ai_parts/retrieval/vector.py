"""
向量检索策略

基于向量相似度的语义检索实现。
"""
import logging
from typing import List, Literal, Optional

from ai_parts.indexing.index_manager import IndexManager

from .base import BaseRetriever, RetrievalQuery, RetrievalResult
from .registry import register

logger = logging.getLogger(__name__)


@register("text", "纯文本向量检索")
class TextVectorRetriever(BaseRetriever):
    """
    文本向量检索

    仅检索 text_index 中的文档（包括 memo 正文和文本附件）。
    """

    def __init__(self, index_manager: IndexManager):
        self.manager = index_manager

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        if self.manager.text_index is None:
            logger.warning("Text index not available")
            return []

        retriever = self.manager.text_index.as_retriever(
            similarity_top_k=query.top_k * 2  # 多取一些用于后续过滤
        )
        nodes = retriever.retrieve(query.query)

        results = [
            RetrievalResult(
                doc_id=node.node_id or "",
                memo_uid=node.metadata.get("memo_uid", ""),
                score=node.score or 0.0,
                content=node.text or "",
                metadata=node.metadata or {},
                source="text",
            )
            for node in nodes
        ]

        # 应用过滤和去重
        results = self.filter_results(results, query.filters, query.min_score)
        results = self.deduplicate_by_memo(results)

        return results[:query.top_k]


@register("image", "纯图片向量检索")
class ImageVectorRetriever(BaseRetriever):
    """
    图片向量检索

    仅检索 image_index 中的文档。
    """

    def __init__(self, index_manager: IndexManager):
        self.manager = index_manager

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        if self.manager.image_index is None:
            logger.warning("Image index not available")
            return []

        retriever = self.manager.image_index.as_retriever(
            similarity_top_k=query.top_k * 2
        )
        nodes = retriever.retrieve(query.query)

        results = [
            RetrievalResult(
                doc_id=node.node_id or "",
                memo_uid=node.metadata.get("memo_uid", ""),
                score=node.score or 0.0,
                content=node.text or "",
                metadata=node.metadata or {},
                source="image",
            )
            for node in nodes
        ]

        results = self.filter_results(results, query.filters, query.min_score)
        results = self.deduplicate_by_memo(results)

        return results[:query.top_k]


@register("vector", "向量检索（文本+图片合并）")
class VectorRetriever(BaseRetriever):
    """
    综合向量检索

    同时检索文本和图片索引，按分数合并排序。
    """

    def __init__(self, index_manager: IndexManager):
        self.manager = index_manager
        self.text_retriever = TextVectorRetriever(index_manager)
        self.image_retriever = ImageVectorRetriever(index_manager)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        # 分别检索
        text_results = self.text_retriever.retrieve(
            RetrievalQuery(
                query=query.query,
                top_k=query.top_k,
                min_score=query.min_score,
                filters=query.filters,
            )
        )

        image_results = self.image_retriever.retrieve(
            RetrievalQuery(
                query=query.query,
                top_k=query.top_k,
                min_score=query.min_score,
                filters=query.filters,
            )
        )

        # 合并并按分数排序
        all_results = text_results + image_results
        all_results.sort(key=lambda x: x.score, reverse=True)

        # 去重
        all_results = self.deduplicate_by_memo(all_results)

        return all_results[:query.top_k]
