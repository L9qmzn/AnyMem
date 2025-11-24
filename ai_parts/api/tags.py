"""
标签生成 API 端点
"""
import logging
from fastapi import APIRouter

from ai_parts.models import TagGenerationRequest, TagGenerationResponse
from ai_parts.services.tag_service import generate_tags_for_memo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


@router.post("/generate", response_model=TagGenerationResponse)
async def generate_tags(request: TagGenerationRequest):
    """为Memo生成AI标签"""
    try:
        logger.info(f"Generating tags for: {request.memo.name or 'unnamed'}")

        ai_tags = await generate_tags_for_memo(
            memo=request.memo,
            user_all_tags=request.user_all_tags,
            max_tags=request.max_tags,
        )

        existing_tags = request.memo.tags or []
        merged_tags = sorted(set(existing_tags + ai_tags))

        logger.info(f"Generated {len(ai_tags)} tags: {ai_tags}")

        return TagGenerationResponse(
            success=True,
            tags=ai_tags,
            merged_tags=merged_tags,
        )

    except Exception as e:
        logger.error(f"Tag generation error: {e}", exc_info=True)
        return TagGenerationResponse(
            success=False,
            tags=[],
            merged_tags=[],
            error=str(e),
        )
