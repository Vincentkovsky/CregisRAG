"""生成模块 - 提供LLM生成服务"""

from .llm_service import LLMService, create_llm_service

__all__ = ["LLMService", "create_llm_service"] 