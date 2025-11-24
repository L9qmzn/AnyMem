"""
检索策略注册表

使用装饰器模式注册检索策略，支持动态获取和列举可用策略。
"""
import logging
from typing import Any, Callable, Dict, List, Type

from .base import BaseRetriever

logger = logging.getLogger(__name__)

# 全局策略注册表
_RETRIEVERS: Dict[str, Type[BaseRetriever]] = {}


def register(name: str, description: str = ""):
    """
    装饰器：注册检索策略

    Args:
        name: 策略名称，用于通过 get_retriever 获取
        description: 策略描述

    Example:
        @register("vector", "纯向量语义检索")
        class VectorRetriever(BaseRetriever):
            ...
    """
    def decorator(cls: Type[BaseRetriever]) -> Type[BaseRetriever]:
        if name in _RETRIEVERS:
            logger.warning(f"Retriever '{name}' already registered, overwriting")

        cls.name = name
        if description:
            cls.description = description

        _RETRIEVERS[name] = cls
        logger.debug(f"Registered retriever: {name} -> {cls.__name__}")
        return cls

    return decorator


def get_retriever(name: str, **kwargs) -> BaseRetriever:
    """
    根据名称获取检索器实例

    Args:
        name: 策略名称
        **kwargs: 传递给检索器构造函数的参数

    Returns:
        检索器实例

    Raises:
        ValueError: 未知的策略名称
    """
    if name not in _RETRIEVERS:
        available = ", ".join(_RETRIEVERS.keys()) or "(none)"
        raise ValueError(f"Unknown retriever: '{name}'. Available: {available}")

    cls = _RETRIEVERS[name]
    return cls(**kwargs)


def list_retrievers() -> List[Dict[str, str]]:
    """
    列出所有已注册的检索策略

    Returns:
        策略信息列表，每个元素包含 name 和 description
    """
    return [
        {"name": name, "description": cls.description}
        for name, cls in _RETRIEVERS.items()
    ]


def has_retriever(name: str) -> bool:
    """检查策略是否已注册"""
    return name in _RETRIEVERS


def get_retriever_class(name: str) -> Type[BaseRetriever]:
    """获取策略类（不实例化）"""
    if name not in _RETRIEVERS:
        raise ValueError(f"Unknown retriever: '{name}'")
    return _RETRIEVERS[name]
