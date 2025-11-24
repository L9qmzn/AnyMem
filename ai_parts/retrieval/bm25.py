"""
BM25 关键词检索策略

基于 LlamaIndex 的 BM25Retriever，支持中文分词。
需要安装: pip install llama-index-retrievers-bm25 jieba
"""
import logging
from typing import Callable, List, Optional

from ai_parts.indexing.index_manager import IndexManager

from .base import BaseRetriever, RetrievalQuery, RetrievalResult
from .registry import register

logger = logging.getLogger(__name__)

# 尝试导入 jieba 用于中文分词
try:
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
        import jieba

    def chinese_tokenizer(text: str) -> List[str]:
        """中文分词器"""
        return list(jieba.cut_for_search(text))

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    chinese_tokenizer = None
    logger.warning("jieba not installed, Chinese tokenization disabled")

# 尝试导入 BM25Retriever
try:
    from llama_index.retrievers.bm25 import BM25Retriever as LlamaBM25Retriever

    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    LlamaBM25Retriever = None
    logger.warning("llama-index-retrievers-bm25 not installed")


class BM25Index:
    """
    BM25 索引管理

    维护一个与向量索引同步的 BM25 索引。
    """

    def __init__(
        self,
        tokenizer: Optional[Callable[[str], List[str]]] = None,
        similarity_top_k: int = 10,
    ):
        if not HAS_BM25:
            raise RuntimeError(
                "BM25 not available. Install with: pip install llama-index-retrievers-bm25"
            )

        self.tokenizer = tokenizer or (chinese_tokenizer if HAS_JIEBA else None)
        self.similarity_top_k = similarity_top_k
        self._retriever: Optional[LlamaBM25Retriever] = None
        self._nodes: List = []

    def build_from_nodes(self, nodes: List) -> None:
        """从节点列表构建 BM25 索引"""
        if not nodes:
            logger.warning("No nodes to build BM25 index")
            return

        self._nodes = nodes

        # 构建 BM25 检索器
        self._retriever = LlamaBM25Retriever.from_defaults(
            nodes=nodes,
            similarity_top_k=self.similarity_top_k,
            tokenizer=self.tokenizer,
        )
        tokenizer_name = "jieba (Chinese)" if self.tokenizer == chinese_tokenizer else (
            "custom" if self.tokenizer else "default (English)"
        )
        logger.info(f"Built BM25 index with {len(nodes)} nodes, tokenizer: {tokenizer_name}")

    def retrieve(self, query: str, top_k: int = 10) -> List:
        """执行 BM25 检索"""
        if self._retriever is None:
            logger.warning("BM25 index not built")
            return []

        # 确保 top_k 不超过语料库大小
        corpus_size = len(self._nodes)
        actual_top_k = min(top_k, corpus_size) if corpus_size > 0 else top_k

        # 临时调整 top_k
        original_top_k = self._retriever.similarity_top_k
        self._retriever.similarity_top_k = actual_top_k

        try:
            results = self._retriever.retrieve(query)
            return results
        finally:
            self._retriever.similarity_top_k = original_top_k

    @property
    def is_ready(self) -> bool:
        return self._retriever is not None and len(self._nodes) > 0


# 全局 BM25 索引实例
_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> Optional[BM25Index]:
    """获取全局 BM25 索引"""
    return _bm25_index


def set_bm25_index(index: BM25Index) -> None:
    """设置全局 BM25 索引"""
    global _bm25_index
    _bm25_index = index


def build_bm25_from_index_manager(
    index_manager: IndexManager,
    tokenizer: Optional[Callable[[str], List[str]]] = None,
) -> BM25Index:
    """
    从 IndexManager 构建 BM25 索引

    遍历 text_index 中的所有节点构建 BM25 索引。
    """
    if not HAS_BM25:
        raise RuntimeError("BM25 not available")

    # 从向量存储获取所有节点
    # 注意：这需要 IndexManager 提供获取所有文档的方法
    # 这里我们通过 docstore 获取
    nodes = []

    try:
        # 尝试从 vector store 获取所有 node ids
        vector_store = index_manager.text_index._vector_store
        # ChromaDB 的方式
        if hasattr(vector_store, "_collection"):
            collection = vector_store._collection
            result = collection.get()
            if result and "documents" in result:
                from llama_index.core.schema import TextNode

                for i, doc_text in enumerate(result["documents"]):
                    metadata = result["metadatas"][i] if result.get("metadatas") else {}
                    node_id = result["ids"][i] if result.get("ids") else f"node_{i}"
                    nodes.append(
                        TextNode(
                            text=doc_text,
                            id_=node_id,
                            metadata=metadata,
                        )
                    )
    except Exception as e:
        logger.error(f"Failed to extract nodes from index: {e}")

    if not nodes:
        logger.warning("No nodes extracted for BM25 index")

    bm25_index = BM25Index(tokenizer=tokenizer)
    if nodes:
        bm25_index.build_from_nodes(nodes)

    return bm25_index


@register("bm25", "BM25 关键词检索")
class BM25Retriever(BaseRetriever):
    """
    BM25 关键词检索

    基于 TF-IDF 的经典关键词匹配，适合精确关键词搜索。
    需要先调用 build_bm25_from_index_manager 构建索引。
    """

    def __init__(
        self,
        index_manager: IndexManager,
        bm25_index: Optional[BM25Index] = None,
    ):
        self.manager = index_manager
        self.bm25_index = bm25_index or get_bm25_index()

        if self.bm25_index is None or not self.bm25_index.is_ready:
            logger.warning("BM25 index not ready, results may be empty")

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        if self.bm25_index is None or not self.bm25_index.is_ready:
            logger.warning("BM25 index not available")
            return []

        nodes = self.bm25_index.retrieve(query.query, top_k=query.top_k * 2)

        results = [
            RetrievalResult(
                doc_id=node.node_id or "",
                memo_uid=node.metadata.get("memo_uid", ""),
                score=node.score or 0.0,
                content=node.text or "",
                metadata=node.metadata or {},
                source="bm25",
            )
            for node in nodes
        ]

        results = self.filter_results(results, query.filters, query.min_score)
        results = self.deduplicate_by_memo(results)

        return results[: query.top_k]
