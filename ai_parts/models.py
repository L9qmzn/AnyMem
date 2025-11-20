"""
AI服务数据模型
"""
from typing import List, Optional, Union
from pydantic import BaseModel, Field

class Attachment(BaseModel):
    """附件模型 - 简化版，只包含AI标签生成需要的字段"""
    name: Optional[str] = None
    filename: Optional[str] = None
    type: Optional[str] = None
    externalLink: Optional[str] = None

    class Config:
        # 允许额外字段，防止验证失败
        extra = "allow"


class MemoProperty(BaseModel):
    """备忘录属性"""
    hasLink: bool = False
    hasTaskList: bool = False
    hasCode: bool = False
    hasIncompleteTasks: bool = False


class Memo(BaseModel):
    """备忘录模型"""
    name: Optional[str] = None
    state: Optional[str] = None
    creator: Optional[str] = None
    createTime: Union[str, dict, None] = None  # 可能是ISO字符串或Date对象
    updateTime: Union[str, dict, None] = None
    displayTime: Union[str, dict, None] = None
    content: str = ""
    visibility: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    aiTags: List[str] = Field(default_factory=list)
    pinned: bool = False
    attachments: List[Attachment] = Field(default_factory=list)
    relations: List = Field(default_factory=list)
    reactions: List = Field(default_factory=list)
    property: Optional[MemoProperty] = None
    snippet: Optional[str] = None

    class Config:
        # 允许额外字段
        extra = "allow"


class TagGenerationRequest(BaseModel):
    """标签生成请求"""
    memo: Memo
    user_all_tags: List[str] = Field(default_factory=list, description="用户所有常用标签")
    max_tags: int = Field(default=5, ge=1, le=20, description="最多生成的标签数量")


class TagGenerationResponse(BaseModel):
    """标签生成响应"""
    success: bool
    tags: List[str] = Field(default_factory=list, description="AI生成的新标签")
    merged_tags: List[str] = Field(default_factory=list, description="合并后的所有标签")
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    version: str
