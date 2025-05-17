"""存储模块 - 提供统一的存储访问层"""

from .storage_service import StorageService, create_storage_service

__all__ = ["StorageService", "create_storage_service"] 