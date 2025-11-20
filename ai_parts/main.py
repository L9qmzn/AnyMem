"""
AI服务 FastAPI 应用
用于提供AI相关功能，目前支持自动生成标签
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from models import (
    TagGenerationRequest,
    TagGenerationResponse,
    HealthResponse,
)
from tag_service import generate_tags_for_memo

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"AI Service starting on {settings.host}:{settings.port}")
    logger.info(f"Using model: {settings.tag_generation_model}")
    yield
    logger.info("AI Service shutting down")


app = FastAPI(
    title="Memos AI Service",
    description="AI服务，提供自动标签生成等功能",
    version="0.1.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        service="memos-ai-service",
        version="0.1.0"
    )


@app.post("/api/v1/tags/generate", response_model=TagGenerationResponse)
async def generate_tags(request: TagGenerationRequest):
    """
    为备忘录生成AI标签

    - **memo**: 备忘录对象，包含内容和附件
    - **user_all_tags**: 用户常用的所有标签列表
    - **max_tags**: 最多生成的标签数量（默认5个）

    返回AI生成的新标签列表和合并后的完整标签列表。
    """
    try:
        logger.info(f"Generating tags for memo: {request.memo.name or 'unnamed'}")

        # 调用异步标签生成服务
        ai_tags = await generate_tags_for_memo(
            memo=request.memo,
            user_all_tags=request.user_all_tags,
            max_tags=request.max_tags,
        )

        # 合并标签
        existing_tags = request.memo.tags or []
        merged_tags = sorted(set(existing_tags + ai_tags))

        logger.info(f"Generated {len(ai_tags)} tags: {ai_tags}")

        return TagGenerationResponse(
            success=True,
            tags=ai_tags,
            merged_tags=merged_tags,
        )

    except Exception as e:
        logger.error(f"Error generating tags: {str(e)}", exc_info=True)
        return TagGenerationResponse(
            success=False,
            tags=[],
            merged_tags=[],
            error=str(e),
        )


@app.get("/")
async def root():
    """根路径，返回服务信息"""
    return {
        "service": "Memos AI Service",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "generate_tags": "/api/v1/tags/generate",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
