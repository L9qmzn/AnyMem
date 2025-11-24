"""
Memos AI Service - 统一的FastAPI应用
提供：
- AI标签生成
- Memo向量索引
- 语义搜索
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_parts.api import indexing, search, tags
from ai_parts.config import get_settings
from ai_parts.core.embeddings import get_jina_embeddings
from ai_parts.indexing.index_manager import IndexManager, create_index_manager
from ai_parts.retrieval import list_retrievers
from ai_parts.retrieval.bm25 import (
    HAS_BM25,
    build_bm25_from_index_manager,
    set_bm25_index,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# 全局索引管理器
_index_manager: Optional[IndexManager] = None


def get_index_manager() -> IndexManager:
    """获取或创建全局索引管理器"""
    global _index_manager
    if _index_manager is None:
        text_embed, image_embed = get_jina_embeddings(settings)
        if text_embed is None:
            from llama_index.core.embeddings import MockEmbedding
            text_embed = MockEmbedding(embed_dim=512)
            image_embed = text_embed

        base_dir = Path(getattr(settings, "index_base_dir", ".memo_indexes/chroma"))
        _index_manager = create_index_manager(
            text_embed_model=text_embed,
            image_embed_model=image_embed,
            base_dir=base_dir,
        )
    return _index_manager


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"AI Service starting on {settings.host}:{settings.port}")
    logger.info(f"Tag model: {settings.tag_generation_model}")

    # 初始化索引管理器
    try:
        manager = get_index_manager()
        status = manager.get_index_status()
        logger.info(f"Index loaded: {status['total_memos']} memos, "
                   f"{status['total_text_vectors']} text, "
                   f"{status['total_image_vectors']} image vectors")

        # 注入索引管理器到各个路由模块
        indexing.set_index_manager(manager)
        search.set_index_manager(manager)

        # 初始化 BM25 索引（可选）
        if HAS_BM25:
            try:
                bm25_index = build_bm25_from_index_manager(manager)
                set_bm25_index(bm25_index)
                if bm25_index.is_ready:
                    logger.info(f"BM25 index built with {len(bm25_index._nodes)} nodes")
                else:
                    logger.warning("BM25 index built but empty")
            except Exception as e:
                logger.warning(f"BM25 index init failed: {e}")
        else:
            logger.info("BM25 not available (install llama-index-retrievers-bm25)")

        # 列出可用的检索策略
        retrievers = list_retrievers()
        logger.info(f"Available retrievers: {[r['name'] for r in retrievers]}")

    except Exception as e:
        logger.warning(f"Index init failed: {e}")

    yield
    logger.info("AI Service shutting down")


# ==================== FastAPI应用 ====================

app = FastAPI(
    title="Memos AI Service",
    description="AI服务：标签生成、向量索引、语义搜索",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tags.router)
app.include_router(indexing.router)
app.include_router(search.router)


# ==================== 基础端点 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        manager = get_index_manager()
        status_info = manager.get_index_status()
        index_ready = True
        total_indexed = status_info["total_memos"]
    except Exception:
        index_ready = False
        total_indexed = 0

    return {
        "status": "healthy",
        "service": "memos-ai-service",
        "version": "1.0.0",
        "index_ready": index_ready,
        "total_indexed_memos": total_indexed,
    }


@app.get("/")
async def root():
    """服务信息"""
    return {
        "service": "Memos AI Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "tags": "/api/v1/tags/generate",
            "search": "/internal/search",
            "index_status": "/internal/index/status",
            "index_memo": "/internal/index/memo",
            "delete_index": "/internal/index/memo/{memo_uid}",
        }
    }


# ==================== 主程序 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_parts.main:app",
        host=settings.host,
        port=settings.port,
        # reload=True,
    )
