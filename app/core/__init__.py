"""
CregisRAG核心模块

该模块包含CregisRAG系统的核心组件，包括:
- RAG引擎: 协调所有子系统的主要引擎
- 嵌入服务: 将文本转换为向量表示
- 向量存储: 存储和检索向量化文本
- 生成服务: 与LLM交互生成回答
- 文档摄入: 处理、分块和索引文档
- 用户反馈: 管理用户对系统回答的反馈
"""

from .rag_engine import RAGEngine, create_rag_engine

__all__ = ["RAGEngine", "create_rag_engine"] 