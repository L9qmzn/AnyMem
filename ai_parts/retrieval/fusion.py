"""
BM25 + Vector 混合检索策略

实现两种融合方式：
1. RRF (Reciprocal Rank Fusion) - 基于排名的融合
2. Alpha 加权融合 - 基于分数的融合
"""
import logging
from typing import Dict, List, Optional

from ai_parts.indexing.index_manager import IndexManager

from .base import BaseRetriever, RetrievalQuery, RetrievalResult
from .bm25 import BM25Index, BM25Retriever, get_bm25_index
from .registry import register
from .vector import TextVectorRetriever

logger = logging.getLogger(__name__)


@register("bm25_vector", "BM25 + Vector RRF 融合")
class BM25VectorFusionRetriever(BaseRetriever):
    """
    BM25 + Vector 混合检索 (RRF 融合)

    结合关键词匹配和语义理解的优势：
    - BM25: 精确关键词匹配，适合专有名词、代码等
    - Vector: 语义相似度，适合同义词、意图理解

    使用 RRF (Reciprocal Rank Fusion) 融合两路结果。
    """

    def __init__(
        self,
        index_manager: IndexManager,
        bm25_index: Optional[BM25Index] = None,
        rrf_k: int = 60,
        bm25_weight: float = 1.0,
        vector_weight: float = 1.0,
    ):
        """
        Args:
            index_manager: 索引管理器
            bm25_index: BM25 索引，如果为 None 则使用全局索引
            rrf_k: RRF 常数，控制排名衰减，默认 60
            bm25_weight: BM25 结果权重
            vector_weight: Vector 结果权重
        """
        self.manager = index_manager
        self.bm25_index = bm25_index or get_bm25_index()
        self.rrf_k = rrf_k
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight

        self.vector_retriever = TextVectorRetriever(index_manager)
        self.bm25_retriever = BM25Retriever(index_manager, self.bm25_index)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        fetch_k = query.top_k * 3

        sub_query = RetrievalQuery(
            query=query.query,
            top_k=fetch_k,
            min_score=0.0,
            filters=query.filters,
        )

        # 两路召回
        vector_results = self.vector_retriever.retrieve(sub_query)
        bm25_results = self.bm25_retriever.retrieve(sub_query)

        logger.debug(
            f"BM25+Vector fusion: vector={len(vector_results)}, bm25={len(bm25_results)}"
        )

        # RRF 融合
        fused = self._rrf_fusion(
            [
                (vector_results, self.vector_weight),
                (bm25_results, self.bm25_weight),
            ]
        )

        # 分数过滤
        if query.min_score > 0:
            fused = [r for r in fused if r.score >= query.min_score]

        return fused[: query.top_k]

    def _rrf_fusion(
        self,
        result_lists: List[tuple[List[RetrievalResult], float]],
    ) -> List[RetrievalResult]:
        """RRF 融合"""
        rrf_scores: Dict[str, float] = {}
        docs: Dict[str, RetrievalResult] = {}

        for results, weight in result_lists:
            for rank, r in enumerate(results):
                uid = r.memo_uid
                if not uid:
                    continue

                rrf_score = weight * (1.0 / (self.rrf_k + rank + 1))
                rrf_scores[uid] = rrf_scores.get(uid, 0.0) + rrf_score

                if uid not in docs:
                    docs[uid] = r

        sorted_uids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        return [
            docs[uid].model_copy(update={"score": rrf_scores[uid], "source": "fusion"})
            for uid in sorted_uids
        ]


@register("bm25_vector_alpha", "BM25 + Vector Alpha 加权融合")
class BM25VectorAlphaRetriever(BaseRetriever):
    """
    BM25 + Vector 混合检索 (Alpha 加权融合)

    使用 alpha 参数控制两路结果的权重：
    - alpha = 0.0: 纯 BM25
    - alpha = 1.0: 纯 Vector
    - alpha = 0.5: 各占一半

    分数计算: score = alpha * vector_score + (1 - alpha) * bm25_score
    """

    def __init__(
        self,
        index_manager: IndexManager,
        bm25_index: Optional[BM25Index] = None,
        alpha: float = 0.5,
    ):
        """
        Args:
            index_manager: 索引管理器
            bm25_index: BM25 索引
            alpha: 融合权重，0.0=纯BM25，1.0=纯Vector，默认 0.5
        """
        self.manager = index_manager
        self.bm25_index = bm25_index or get_bm25_index()
        self.alpha = max(0.0, min(1.0, alpha))  # 限制在 [0, 1]

        self.vector_retriever = TextVectorRetriever(index_manager)
        self.bm25_retriever = BM25Retriever(index_manager, self.bm25_index)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        fetch_k = query.top_k * 3

        sub_query = RetrievalQuery(
            query=query.query,
            top_k=fetch_k,
            min_score=0.0,
            filters=query.filters,
        )

        vector_results = self.vector_retriever.retrieve(sub_query)
        bm25_results = self.bm25_retriever.retrieve(sub_query)

        # 归一化分数
        vector_results = self._normalize_scores(vector_results)
        bm25_results = self._normalize_scores(bm25_results)

        # Alpha 加权融合
        fused = self._alpha_fusion(vector_results, bm25_results)

        if query.min_score > 0:
            fused = [r for r in fused if r.score >= query.min_score]

        return fused[: query.top_k]

    def _normalize_scores(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Min-Max 归一化到 [0, 1]"""
        if not results:
            return results

        scores = [r.score for r in results]
        min_score, max_score = min(scores), max(scores)

        if max_score == min_score:
            return [r.model_copy(update={"score": 1.0}) for r in results]

        return [
            r.model_copy(
                update={"score": (r.score - min_score) / (max_score - min_score)}
            )
            for r in results
        ]

    def _alpha_fusion(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """Alpha 加权融合"""
        scores: Dict[str, float] = {}
        docs: Dict[str, RetrievalResult] = {}

        # Vector 分数 (权重 alpha)
        for r in vector_results:
            if r.memo_uid:
                scores[r.memo_uid] = self.alpha * r.score
                docs[r.memo_uid] = r

        # BM25 分数 (权重 1-alpha)
        for r in bm25_results:
            if r.memo_uid:
                scores[r.memo_uid] = scores.get(r.memo_uid, 0.0) + (1 - self.alpha) * r.score
                if r.memo_uid not in docs:
                    docs[r.memo_uid] = r

        sorted_uids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [
            docs[uid].model_copy(update={"score": scores[uid], "source": "fusion"})
            for uid in sorted_uids
        ]


@register("adaptive", "自适应混合检索")
class AdaptiveRetriever(BaseRetriever):
    """
    自适应混合检索

    根据查询特征动态调整 BM25 和 Vector 的权重：
    - 短查询（关键词风格）: 偏向 BM25
    - 长查询（自然语言）: 偏向 Vector
    - 包含特殊字符/代码: 偏向 BM25
    """

    def __init__(
        self,
        index_manager: IndexManager,
        bm25_index: Optional[BM25Index] = None,
        base_alpha: float = 0.5,
    ):
        self.manager = index_manager
        self.bm25_index = bm25_index or get_bm25_index()
        self.base_alpha = base_alpha

        self.vector_retriever = TextVectorRetriever(index_manager)
        self.bm25_retriever = BM25Retriever(index_manager, self.bm25_index)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        # 动态计算 alpha
        alpha = self._compute_alpha(query.query)
        logger.debug(f"Adaptive alpha for query '{query.query[:30]}...': {alpha:.2f}")

        fetch_k = query.top_k * 3
        sub_query = RetrievalQuery(
            query=query.query,
            top_k=fetch_k,
            min_score=0.0,
            filters=query.filters,
        )

        vector_results = self.vector_retriever.retrieve(sub_query)
        bm25_results = self.bm25_retriever.retrieve(sub_query)

        # 归一化
        vector_results = self._normalize_scores(vector_results)
        bm25_results = self._normalize_scores(bm25_results)

        # 融合
        fused = self._alpha_fusion(vector_results, bm25_results, alpha)

        if query.min_score > 0:
            fused = [r for r in fused if r.score >= query.min_score]

        return fused[: query.top_k]

    def _compute_alpha(self, query: str) -> float:
        """
        根据查询特征计算 alpha

        返回值越高越偏向 Vector，越低越偏向 BM25
        """
        alpha = self.base_alpha

        # 查询长度影响
        words = query.split()
        if len(words) <= 2:
            # 短查询，偏向 BM25
            alpha -= 0.2
        elif len(words) >= 8:
            # 长查询，偏向 Vector
            alpha += 0.15

        # 特殊字符检测（代码、路径等）
        special_chars = set("{}[]()<>=/\\|@#$%^&*`~")
        if any(c in query for c in special_chars):
            alpha -= 0.25

        # 引号检测（精确匹配意图）
        if '"' in query or "'" in query:
            alpha -= 0.3

        # 限制在 [0.1, 0.9]
        return max(0.1, min(0.9, alpha))

    def _normalize_scores(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        if not results:
            return results

        scores = [r.score for r in results]
        min_score, max_score = min(scores), max(scores)

        if max_score == min_score:
            return [r.model_copy(update={"score": 1.0}) for r in results]

        return [
            r.model_copy(
                update={"score": (r.score - min_score) / (max_score - min_score)}
            )
            for r in results
        ]

    def _alpha_fusion(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        alpha: float,
    ) -> List[RetrievalResult]:
        scores: Dict[str, float] = {}
        docs: Dict[str, RetrievalResult] = {}

        for r in vector_results:
            if r.memo_uid:
                scores[r.memo_uid] = alpha * r.score
                docs[r.memo_uid] = r

        for r in bm25_results:
            if r.memo_uid:
                scores[r.memo_uid] = scores.get(r.memo_uid, 0.0) + (1 - alpha) * r.score
                if r.memo_uid not in docs:
                    docs[r.memo_uid] = r

        sorted_uids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [
            docs[uid].model_copy(update={"score": scores[uid], "source": "adaptive"})
            for uid in sorted_uids
        ]
