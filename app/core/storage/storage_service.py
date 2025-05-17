"""
存储服务模块

该模块提供统一的存储访问层，负责处理向量数据库、文本索引等存储相关操作。
"""
import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

from app.core.ingest.document_processor import Document, DocumentChunk
from app.core.retrieval.vector_store import VectorStore, create_vector_store

logger = logging.getLogger(__name__)

class StorageService:
    """
    存储服务类
    
    提供对文档、向量和元数据的统一存储访问。
    支持向量搜索、混合搜索和文档检索等功能。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化存储服务
        
        Args:
            config: 包含存储服务配置的字典
        """
        self.config = config
        
        # 初始化向量存储
        vector_store_config = config.get("vector_store", {})
        self.vector_store = create_vector_store(vector_store_config)
        
        # 初始化文本索引 (可选)
        self.text_index = None
        if config.get("use_text_index", False):
            # 如果启用了文本索引，则在这里创建
            pass
            
        # 索引配置
        self.normalize_embeddings = config.get("normalize_embeddings", True)
        
        logger.info("存储服务初始化完成")
    
    async def initialize(self) -> bool:
        """
        初始化存储服务
        
        Returns:
            初始化是否成功
        """
        try:
            # 初始化向量存储
            if not await self.vector_store.initialize():
                logger.error("向量存储初始化失败")
                return False
                
            # 初始化文本索引 (如果启用)
            if self.text_index is not None:
                # 初始化文本索引逻辑
                pass
                
            logger.info("存储服务初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"存储服务初始化失败: {str(e)}")
            return False
    
    async def add_documents(self, documents: List[Document]) -> Tuple[int, int]:
        """
        将文档添加到存储服务
        
        Args:
            documents: 文档列表
            
        Returns:
            成功添加的文档数量和文档片段数量
        """
        start_time = time.time()
        added_docs = 0
        added_chunks = 0
        
        try:
            # 向向量存储添加文档
            docs_count, chunks_count = await self.vector_store.add_documents(documents)
            added_docs += docs_count
            added_chunks += chunks_count
            
            # 更新文本索引 (如果启用)
            if self.text_index is not None:
                # 更新文本索引逻辑
                pass
                
            process_time = time.time() - start_time
            logger.info(f"添加文档完成: {added_docs}个文档, {added_chunks}个片段, 耗时: {process_time:.2f}秒")
            
            return added_docs, added_chunks
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            return added_docs, added_chunks
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        获取文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档对象或None
        """
        try:
            return await self.vector_store.get_document(document_id)
        except Exception as e:
            logger.error(f"获取文档失败: {str(e)}")
            return None
    
    async def get_document_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        """
        获取文档片段
        
        Args:
            chunk_id: 文档片段ID
            
        Returns:
            文档片段对象或None
        """
        try:
            return await self.vector_store.get_document_chunk(chunk_id)
        except Exception as e:
            logger.error(f"获取文档片段失败: {str(e)}")
            return None
    
    async def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            删除是否成功
        """
        try:
            # 从向量存储中删除
            success = await self.vector_store.delete_document(document_id)
            
            # 从文本索引中删除 (如果启用)
            if self.text_index is not None:
                # 从文本索引删除文档逻辑
                pass
                
            return success
            
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return False
    
    async def vector_search(self, query_embedding: np.ndarray, 
                           limit: int = 5, 
                           metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行向量搜索
        
        Args:
            query_embedding: 查询的嵌入向量
            limit: 返回结果的最大数量
            metadata_filter: 元数据过滤条件
            
        Returns:
            搜索结果列表
        """
        try:
            # 检查向量存储是否初始化
            if not self.vector_store:
                logger.error("向量存储未初始化")
                return []
                
            # 确保向量存储的集合已初始化
            if hasattr(self.vector_store, 'collection') and self.vector_store.collection is None:
                logger.error("向量存储集合未初始化，尝试重新初始化")
                if not await self.vector_store.initialize():
                    logger.error("向量存储初始化失败")
                    return []
            
            # 向量归一化 (如果配置中启用)
            if self.normalize_embeddings:
                norm = np.linalg.norm(query_embedding)
                if norm > 0:
                    query_embedding = query_embedding / norm
            
            # 执行向量相似度搜索
            results = await self.vector_store.similarity_search(
                query_embedding,
                top_k=limit,
                filter=metadata_filter
            )
            
            # 将结果转换为统一格式
            formatted_results = []
            for result in results:
                formatted_result = {
                    "id": result.get("id", ""),
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity": result.get("similarity", 0)
                }
                
                # 如果结果包含向量，可以添加到结果中，用于后续处理 (如MMR)
                if "vector" in result:
                    formatted_result["vector"] = result["vector"]
                    
                formatted_results.append(formatted_result)
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    async def text_search(self, query: str, 
                         limit: int = 5, 
                         metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行文本搜索 (基于关键词/BM25等)
        
        Args:
            query: 文本查询
            limit: 返回结果的最大数量
            metadata_filter: 元数据过滤条件
            
        Returns:
            搜索结果列表
        """
        if self.text_index is None:
            logger.warning("文本索引未启用，无法执行文本搜索")
            return []
            
        try:
            # 执行文本搜索逻辑
            # 在此实现的简单版本中，可以临时使用向量存储的关键词搜索功能
            results = await self.vector_store.keyword_search(
                query,
                top_k=limit,
                filter=metadata_filter
            )
            
            # 将结果转换为统一格式
            formatted_results = []
            for result in results:
                formatted_result = {
                    "id": result.get("id", ""),
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("score", 0)  # 文本搜索得分
                }
                formatted_results.append(formatted_result)
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"文本搜索失败: {str(e)}")
            return []
    
    async def hybrid_search(self, query: str, 
                           query_embedding: np.ndarray,
                           limit: int = 5, 
                           metadata_filter: Optional[Dict[str, Any]] = None,
                           hybrid_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        执行混合搜索 (向量搜索 + 文本搜索)
        
        Args:
            query: 文本查询
            query_embedding: 查询的嵌入向量
            limit: 返回结果的最大数量
            metadata_filter: 元数据过滤条件
            hybrid_weight: 文本搜索结果的权重 (0.0-1.0)
            
        Returns:
            混合搜索结果列表
        """
        try:
            # 检查向量存储是否初始化
            if not self.vector_store:
                logger.error("向量存储未初始化")
                return []
                
            # 确保向量存储的集合已初始化
            if hasattr(self.vector_store, 'collection') and self.vector_store.collection is None:
                logger.error("向量存储集合未初始化，尝试重新初始化")
                if not await self.vector_store.initialize():
                    logger.error("向量存储初始化失败")
                    return []
            
            # 获取向量搜索结果
            vector_results = await self.vector_search(
                query_embedding=query_embedding,
                limit=limit * 2,  # 获取更多候选，以便后续合并
                metadata_filter=metadata_filter
            )
            
            # 获取文本搜索结果 (如果文本索引可用)
            if self.text_index is not None and hybrid_weight > 0:
                text_results = await self.text_search(
                    query=query,
                    limit=limit * 2,  # 获取更多候选，以便后续合并
                    metadata_filter=metadata_filter
                )
            else:
                # 如果没有文本索引或权重为0，则仅使用向量搜索结果
                return vector_results[:limit]
            
            # 合并结果并计算混合得分
            result_map = {}
            
            # 添加向量搜索结果
            for result in vector_results:
                result_id = result["id"]
                if result_id not in result_map:
                    result_map[result_id] = {
                        "id": result_id,
                        "content": result.get("content", ""),
                        "metadata": result.get("metadata", {}),
                        "vector_similarity": result.get("similarity", 0),
                        "text_score": 0,
                        "hybrid_score": (1 - hybrid_weight) * result.get("similarity", 0)
                    }
                    # 保留向量，如果有的话
                    if "vector" in result:
                        result_map[result_id]["vector"] = result["vector"]
            
            # 添加文本搜索结果并计算混合得分
            max_text_score = max([result.get("score", 0) for result in text_results], default=1)
            
            for result in text_results:
                result_id = result["id"]
                normalized_text_score = result.get("score", 0) / max_text_score if max_text_score > 0 else 0
                
                if result_id in result_map:
                    # 更新已存在的结果
                    result_map[result_id]["text_score"] = normalized_text_score
                    result_map[result_id]["hybrid_score"] += hybrid_weight * normalized_text_score
                else:
                    # 添加新结果
                    result_map[result_id] = {
                        "id": result_id,
                        "content": result.get("content", ""),
                        "metadata": result.get("metadata", {}),
                        "vector_similarity": 0,
                        "text_score": normalized_text_score,
                        "hybrid_score": hybrid_weight * normalized_text_score
                    }
            
            # 按混合得分排序
            hybrid_results = list(result_map.values())
            hybrid_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
            
            # 取前K个结果并重新格式化
            top_results = hybrid_results[:limit]
            formatted_results = []
            
            for result in top_results:
                formatted_result = {
                    "id": result["id"],
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "similarity": result["hybrid_score"]  # 使用混合得分作为相似度
                }
                
                # 保留向量，如果有的话
                if "vector" in result:
                    formatted_result["vector"] = result["vector"]
                    
                formatted_results.append(formatted_result)
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            return []
    
    async def get_all_documents_metadata(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        获取所有文档的元数据
        
        Args:
            batch_size: 批处理大小
            
        Returns:
            包含所有文档元数据的列表
        """
        try:
            return await self.vector_store.get_all_documents_metadata(batch_size)
        except Exception as e:
            logger.error(f"获取所有文档元数据失败: {str(e)}")
            return []
    
    async def document_exists(self, document_id: str) -> bool:
        """
        检查文档是否存在
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档是否存在
        """
        try:
            return await self.vector_store.document_exists(document_id)
        except Exception as e:
            logger.error(f"检查文档是否存在失败: {str(e)}")
            return False


def create_storage_service(config: Dict[str, Any]) -> StorageService:
    """
    创建存储服务实例
    
    Args:
        config: 存储服务配置
        
    Returns:
        存储服务实例
    """
    return StorageService(config) 