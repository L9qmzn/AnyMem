"""
检索策略基类定义
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    """单条检索结果"""
    doc_id: str = Field(description="文档ID")
    memo_uid: str = Field(description="Memo唯一标识，如 memos/abc123")
    score: float = Field(description="相关性分数")
    content: str = Field(default="", description="文档内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    source: str = Field(default="text", description="来源: text/image/attachment")


class RetrievalQuery(BaseModel):
    """检索查询参数"""
    query: str = Field(description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    min_score: float = Field(default=0.0, description="最低分数阈值")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="过滤条件")


class BaseRetriever(ABC):
    """
    检索策略抽象基类

    所有检索策略必须继承此类并实现 retrieve 方法。
    """

    # 策略名称，由 @register 装饰器设置
    name: str = "base"

    # 策略描述
    description: str = "Base retriever"

    @abstractmethod
    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """
        执行检索

        Args:
            query: 检索查询参数

        Returns:
            检索结果列表，按相关性分数降序排列
        """
        pass

    def filter_results(
        self,
        results: List[RetrievalResult],
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> List[RetrievalResult]:
        """
        通用结果过滤

        Args:
            results: 原始结果列表
            filters: 过滤条件，如 {"creator": "users/1"}
            min_score: 最低分数阈值
        """
        filtered = []
        for r in results:
            # 分数过滤
            if r.score < min_score:
                continue

            # 元数据过滤
            if filters:
                match = True
                for key, value in filters.items():
                    if key in r.metadata and r.metadata[key] != value:
                        match = False
                        break
                if not match:
                    continue

            filtered.append(r)

        return filtered

    def deduplicate_by_memo(
        self,
        results: List[RetrievalResult],
    ) -> List[RetrievalResult]:
        """
        按 memo_uid 去重，保留最高分结果
        """
        seen = {}
        for r in results:
            if r.memo_uid not in seen or r.score > seen[r.memo_uid].score:
                seen[r.memo_uid] = r

        # 按分数重新排序
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)

    def __repr__(self):
        return f"<{self.__class__.__name__} name='{self.name}'>"
