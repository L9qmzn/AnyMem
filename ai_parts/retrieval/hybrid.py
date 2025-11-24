"""
混合检索策略

实现多种融合策略：RRF、加权融合等。
"""
import logging
from typing import Dict, List, Optional

from ai_parts.indexing.index_manager import IndexManager

from .base import BaseRetriever, RetrievalQuery, RetrievalResult
from .registry import register
from .vector import ImageVectorRetriever, TextVectorRetriever

logger = logging.getLogger(__name__)


@register("hybrid", "混合检索（简单合并）")
class HybridRetriever(BaseRetriever):
    """
    简单混合检索

    分别检索文本和图片，按原始分数合并排序。
    这是原有实现的等效版本。
    """

    def __init__(self, index_manager: IndexManager):
        self.manager = index_manager
        self.text_retriever = TextVectorRetriever(index_manager)
        self.image_retriever = ImageVectorRetriever(index_manager)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        # 分别检索（不应用过滤，最后统一处理）
        sub_query = RetrievalQuery(
            query=query.query,
            top_k=query.top_k,
            min_score=0.0,  # 先不过滤
            filters=None,
        )

        text_results = self.text_retriever.retrieve(sub_query)
        image_results = self.image_retriever.retrieve(sub_query)

        # 合并
        all_results = text_results + image_results
        all_results.sort(key=lambda x: x.score, reverse=True)

        # 应用过滤
        all_results = self.filter_results(all_results, query.filters, query.min_score)
        all_results = self.deduplicate_by_memo(all_results)

        return all_results[:query.top_k]


@register("rrf", "RRF 倒数排名融合")
class RRFRetriever(BaseRetriever):
    """
    Reciprocal Rank Fusion (RRF) 检索

    使用 RRF 算法融合多个检索结果列表。
    RRF 分数 = Σ 1/(k + rank)，其中 k 是常数（默认60）。

    优点：
    - 对不同来源的分数无需归一化
    - 能有效融合多个排序列表
    """

    def __init__(
        self,
        index_manager: IndexManager,
        k: int = 60,
        text_weight: float = 1.0,
        image_weight: float = 1.0,
    ):
        """
        Args:
            index_manager: 索引管理器
            k: RRF 常数，控制排名衰减速度，默认 60
            text_weight: 文本结果权重
            image_weight: 图片结果权重
        """
        self.manager = index_manager
        self.k = k
        self.text_weight = text_weight
        self.image_weight = image_weight
        self.text_retriever = TextVectorRetriever(index_manager)
        self.image_retriever = ImageVectorRetriever(index_manager)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        # 多取一些结果用于融合
        fetch_k = query.top_k * 3

        sub_query = RetrievalQuery(
            query=query.query,
            top_k=fetch_k,
            min_score=0.0,
            filters=query.filters,  # 在子查询中就过滤
        )

        text_results = self.text_retriever.retrieve(sub_query)
        image_results = self.image_retriever.retrieve(sub_query)

        # RRF 融合
        fused = self._rrf_fusion(
            [
                (text_results, self.text_weight),
                (image_results, self.image_weight),
            ]
        )

        # 分数过滤（RRF 分数与原始分数不同，可能需要调整阈值）
        if query.min_score > 0:
            fused = [r for r in fused if r.score >= query.min_score]

        return fused[:query.top_k]

    def _rrf_fusion(
        self,
        result_lists: List[tuple[List[RetrievalResult], float]],
    ) -> List[RetrievalResult]:
        """
        RRF 融合多个结果列表

        Args:
            result_lists: [(results, weight), ...] 每个列表及其权重

        Returns:
            融合后的结果列表，按 RRF 分数排序
        """
        rrf_scores: Dict[str, float] = {}
        docs: Dict[str, RetrievalResult] = {}

        for results, weight in result_lists:
            for rank, r in enumerate(results):
                uid = r.memo_uid
                if not uid:
                    continue

                # RRF 公式：weight * 1/(k + rank + 1)
                rrf_score = weight * (1.0 / (self.k + rank + 1))
                rrf_scores[uid] = rrf_scores.get(uid, 0.0) + rrf_score

                # 保留原始文档信息（取第一次出现的）
                if uid not in docs:
                    docs[uid] = r

        # 按 RRF 分数排序
        sorted_uids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        return [
            docs[uid].model_copy(update={"score": rrf_scores[uid]})
            for uid in sorted_uids
        ]


@register("weighted", "加权融合检索")
class WeightedRetriever(BaseRetriever):
    """
    加权融合检索

    将不同来源的分数归一化后加权求和。
    """

    def __init__(
        self,
        index_manager: IndexManager,
        text_weight: float = 0.7,
        image_weight: float = 0.3,
    ):
        """
        Args:
            index_manager: 索引管理器
            text_weight: 文本结果权重，默认 0.7
            image_weight: 图片结果权重，默认 0.3
        """
        self.manager = index_manager
        self.text_weight = text_weight
        self.image_weight = image_weight
        self.text_retriever = TextVectorRetriever(index_manager)
        self.image_retriever = ImageVectorRetriever(index_manager)

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        fetch_k = query.top_k * 3

        sub_query = RetrievalQuery(
            query=query.query,
            top_k=fetch_k,
            min_score=0.0,
            filters=query.filters,
        )

        text_results = self.text_retriever.retrieve(sub_query)
        image_results = self.image_retriever.retrieve(sub_query)

        # 归一化分数
        text_results = self._normalize_scores(text_results)
        image_results = self._normalize_scores(image_results)

        # 加权融合
        fused = self._weighted_fusion(
            text_results, self.text_weight,
            image_results, self.image_weight,
        )

        if query.min_score > 0:
            fused = [r for r in fused if r.score >= query.min_score]

        return fused[:query.top_k]

    def _normalize_scores(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Min-Max 归一化分数到 [0, 1]"""
        if not results:
            return results

        scores = [r.score for r in results]
        min_score, max_score = min(scores), max(scores)

        if max_score == min_score:
            # 所有分数相同，归一化为 1
            return [r.model_copy(update={"score": 1.0}) for r in results]

        return [
            r.model_copy(update={
                "score": (r.score - min_score) / (max_score - min_score)
            })
            for r in results
        ]

    def _weighted_fusion(
        self,
        results1: List[RetrievalResult], weight1: float,
        results2: List[RetrievalResult], weight2: float,
    ) -> List[RetrievalResult]:
        """加权融合两个结果列表"""
        scores: Dict[str, float] = {}
        docs: Dict[str, RetrievalResult] = {}

        for r in results1:
            if r.memo_uid:
                scores[r.memo_uid] = r.score * weight1
                docs[r.memo_uid] = r

        for r in results2:
            if r.memo_uid:
                scores[r.memo_uid] = scores.get(r.memo_uid, 0.0) + r.score * weight2
                if r.memo_uid not in docs:
                    docs[r.memo_uid] = r

        sorted_uids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [
            docs[uid].model_copy(update={"score": scores[uid]})
            for uid in sorted_uids
        ]
