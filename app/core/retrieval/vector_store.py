"""
向量存储模块

该模块提供向量数据库接口和实现，用于存储和检索文本嵌入。
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, Union
import numpy as np
from abc import ABC, abstractmethod

# 配置日志
logger = logging.getLogger(__name__)

class VectorStore(ABC):
    """
    向量存储抽象基类
    
    定义了向量数据库的通用接口。
    """
    
    @abstractmethod
    async def add_documents(self, 
                     documents: List[Dict[str, Any]], 
                     embeddings: Optional[List[np.ndarray]] = None) -> List[str]:
        """
        添加文档及其嵌入到向量存储
        
        Args:
            documents: 文档列表，每个文档包含文本和元数据
            embeddings: 可选的预计算嵌入
            
        Returns:
            添加文档的ID列表
        """
        pass
    
    @abstractmethod
    async def similarity_search(self, 
                         query_embedding: np.ndarray, 
                         top_k: int = 5, 
                         threshold: float = 0.0,
                         filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        基于向量相似度搜索文档
        
        Args:
            query_embedding: 查询向量
            top_k: 返回的最大结果数
            threshold: 相似度阈值，只返回相似度高于此值的结果
            filter: 元数据过滤条件
            
        Returns:
            匹配文档列表，按相似度降序排序
        """
        pass
    
    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    async def get_document_chunk(self, chunk_id: str) -> Optional[Any]:
        """
        获取文档片段
        
        Args:
            chunk_id: 文档片段ID
            
        Returns:
            文档片段对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """
        删除文档
        
        Args:
            document_ids: 要删除的文档ID列表
            
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
    async def document_exists(self, document_id: str) -> bool:
        """
        检查文档是否存在
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档是否存在
        """
        pass
    
    @abstractmethod
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            包含统计信息的字典
        """
        pass
        
    @abstractmethod
    async def get_all_documents_metadata(self) -> List[Dict[str, Any]]:
        """
        获取所有文档的元数据
        
        Returns:
            包含所有文档元数据的列表
        """
        pass


class ChromaVectorStore(VectorStore):
    """
    基于Chroma的向量存储实现
    
    使用Chroma作为向量数据库后端。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Chroma向量存储
        
        Args:
            config: 配置参数
        """
        self.config = config
        self.chroma_client = None
        self.collection = None
        
        # 读取配置
        self.persist_directory = config.get("persist_directory", "./data/chroma")
        self.collection_name = config.get("collection_name", "documents")
        self.embedding_dimension = config.get("embedding_dimension", 1536)
        
        logger.info(f"初始化Chroma向量存储: 集合={self.collection_name}, 持久化目录={self.persist_directory}")
    
    async def initialize(self) -> bool:
        """
        初始化Chroma客户端和集合
        
        Returns:
            初始化是否成功
        """
        try:
            # 导入Chroma
            import chromadb
            from chromadb.config import Settings
            
            # 确保目录存在
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # 初始化客户端
            self.chroma_client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 获取或创建集合
            try:
                self.collection = self.chroma_client.get_collection(name=self.collection_name)
                logger.info(f"已连接到现有集合: {self.collection_name}")
            except Exception:
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"dimension": self.embedding_dimension}
                )
                logger.info(f"已创建新集合: {self.collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Chroma初始化失败: {str(e)}")
            return False
    
    async def add_documents(self, 
                     documents: List[Dict[str, Any]], 
                     embeddings: Optional[List[np.ndarray]] = None) -> List[str]:
        """
        添加文档及其嵌入到Chroma
        
        Args:
            documents: 文档列表，每个文档包含文本和元数据
            embeddings: 可选的预计算嵌入
            
        Returns:
            添加文档的ID列表
        """
        if not documents:
            logger.warning("尝试添加空文档列表")
            return []
        
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        start_time = time.time()
        
        try:
            # 准备添加数据
            ids = []
            texts = []
            metadatas = []
            embedding_list = []
            
            for i, doc in enumerate(documents):
                # 生成或使用提供的ID
                doc_id = doc.get("id", f"doc_{int(time.time())}_{i}")
                ids.append(doc_id)
                
                # 获取文本和元数据
                texts.append(doc["text"])
                
                # 确保元数据只包含Chroma支持的类型
                # Chroma只支持字符串、整数、浮点数和布尔值
                metadata = doc.get("metadata", {})
                clean_metadata = {k: v for k, v in metadata.items() 
                                 if isinstance(v, (str, int, float, bool))}
                metadatas.append(clean_metadata)
                
                # 如果提供了嵌入，添加到列表
                if embeddings and i < len(embeddings):
                    embedding_list.append(embeddings[i].tolist())
            
            # 添加到Chroma
            if embedding_list and len(embedding_list) == len(ids):
                # 如果提供了所有嵌入，使用它们
                self.collection.add(
                    ids=ids,
                    documents=texts,
                    embeddings=embedding_list,
                    metadatas=metadatas
                )
            else:
                # 否则让Chroma计算嵌入
                self.collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas
                )
            
            logger.info(f"已添加 {len(ids)} 个文档到Chroma, 耗时: {time.time() - start_time:.2f}秒")
            return ids
            
        except Exception as e:
            logger.error(f"向Chroma添加文档失败: {str(e)}")
            return []
    
    async def similarity_search(self, 
                         query_embedding: np.ndarray, 
                         top_k: int = 5, 
                         threshold: float = 0.0,
                         filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        基于向量相似度搜索文档
        
        Args:
            query_embedding: 查询向量
            top_k: 返回的最大结果数
            threshold: 相似度阈值，只返回相似度高于此值的结果
            filter: 元数据过滤条件
            
        Returns:
            匹配文档列表，按相似度降序排序
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        start_time = time.time()
        
        try:
            # 执行查询
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                where=filter  # Chroma的元数据过滤
            )
            
            # 处理结果
            documents = []
            
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    # 获取相似度得分和原始距离
                    # Chroma返回的是L2距离，转换为余弦相似度（简化计算）
                    distance = results["distances"][0][i] if "distances" in results and results["distances"] else 0
                    # 假设归一化向量上的L2距离与余弦相似度有简单关系
                    # 距离越小相似度越高
                    similarity = 1.0 - min(distance / 2.0, 1.0)  # 简化的转换
                    
                    # 应用相似度阈值
                    if similarity < threshold:
                        continue
                    
                    # 创建结果文档
                    document = {
                        "id": doc_id,  # 使用id字段而不是document_id
                        "text": results["documents"][0][i] if "documents" in results and results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if "metadatas" in results and results["metadatas"] else {},
                        "similarity": similarity  # 使用similarity字段而不是score
                    }
                    
                    documents.append(document)
                
                # 添加调试日志
                if documents:
                    logger.info(f"第一个文档结构: {documents[0]}")
            
            logger.info(f"相似度搜索完成, 匹配 {len(documents)} 个文档, 耗时: {time.time() - start_time:.2f}秒")
            return documents
            
        except Exception as e:
            logger.error(f"Chroma相似度搜索失败: {str(e)}")
            return []
    
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        按ID获取文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档及其元数据，如果不存在则为None
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        try:
            result = self.collection.get(ids=[document_id])
            
            if result and result["ids"] and len(result["ids"]) > 0:
                return {
                    "document_id": result["ids"][0],
                    "text": result["documents"][0] if "documents" in result and result["documents"] else "",
                    "metadata": result["metadatas"][0] if "metadatas" in result and result["metadatas"] else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"从Chroma获取文档失败: {str(e)}")
            return None
    
    async def get_document_chunk(self, chunk_id: str) -> Optional[Any]:
        """
        获取文档片段
        
        Args:
            chunk_id: 文档片段ID
            
        Returns:
            文档片段对象，如果不存在则返回None
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        try:
            from app.core.ingest.document_processor import DocumentChunk
            
            result = self.collection.get(ids=[chunk_id])
            
            if result and result["ids"] and len(result["ids"]) > 0:
                # 创建并返回DocumentChunk对象
                metadata = result["metadatas"][0] if "metadatas" in result and result["metadatas"] else {}
                text = result["documents"][0] if "documents" in result and result["documents"] else ""
                
                return DocumentChunk(
                    id=chunk_id,
                    document_id=metadata.get("document_id", ""),
                    content=text,
                    metadata=metadata
                )
            
            return None
            
        except Exception as e:
            logger.error(f"从Chroma获取文档片段失败: {str(e)}")
            return None
    
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """
        删除文档
        
        Args:
            document_ids: 要删除的文档ID列表
            
        Returns:
            操作是否成功
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        if not document_ids:
            logger.warning("尝试删除空ID列表")
            return True
        
        try:
            self.collection.delete(ids=document_ids)
            logger.info(f"已从Chroma删除 {len(document_ids)} 个文档")
            return True
            
        except Exception as e:
            logger.error(f"从Chroma删除文档失败: {str(e)}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            包含统计信息的字典
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
        
        try:
            # 获取基本信息
            count = self.collection.count()
            
            stats = {
                "document_count": count,
                "collection_name": self.collection_name,
                "provider": "chroma"
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取Chroma统计信息失败: {str(e)}")
            return {
                "document_count": 0,
                "collection_name": self.collection_name,
                "provider": "chroma",
                "error": str(e)
            }
            
    async def document_exists(self, document_id: str) -> bool:
        """
        检查文档是否存在
        
        Args:
            document_id: 文档ID
            
        Returns:
            文档是否存在
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
            
        try:
            # 尝试获取文档
            result = self.collection.get(ids=[document_id], include=[])
            # 如果找到文档，ids列表中会有该ID
            return bool(result["ids"]) and document_id in result["ids"]
        except Exception as e:
            logger.error(f"检查文档存在性时出错: {str(e)}")
            return False
            
    async def get_all_documents_metadata(self) -> List[Dict[str, Any]]:
        """
        获取所有文档的元数据
        
        Returns:
            包含所有文档元数据的列表
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
            
        try:
            # 获取集合中的所有文档
            result = self.collection.get(include=["metadatas", "documents"])
            
            documents = []
            if result and "ids" in result and result["ids"]:
                for i, doc_id in enumerate(result["ids"]):
                    metadata = result["metadatas"][i] if "metadatas" in result and result["metadatas"] else {}
                    # 确保metadata是一个字典
                    if not isinstance(metadata, dict):
                        metadata = {}
                    
                    # 添加文档ID
                    metadata["document_id"] = doc_id
                    
                    # 如果有文档内容，添加一个文档预览
                    if "documents" in result and result["documents"] and i < len(result["documents"]):
                        text = result["documents"][i]
                        if text:
                            # 添加文本预览(限制长度)
                            metadata["preview"] = text[:200] + "..." if len(text) > 200 else text
                    
                    documents.append(metadata)
            
            logger.info(f"已检索 {len(documents)} 个文档的元数据")
            return documents
            
        except Exception as e:
            logger.error(f"获取所有文档元数据失败: {str(e)}")
            return []
    
    async def get_document_count(self) -> int:
        """
        获取文档数量
        
        Returns:
            文档数量
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
            
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"获取文档数量失败: {str(e)}")
            return 0
    
    async def get_vector_count(self) -> int:
        """
        获取向量数量
        
        Returns:
            向量数量（在Chroma中通常与文档数量相同）
        """
        if not self.collection:
            raise ValueError("Chroma集合未初始化")
            
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"获取向量数量失败: {str(e)}")
            return 0


def create_vector_store(config: Dict[str, Any]) -> VectorStore:
    """
    从配置创建向量存储
    
    支持多种向量存储实现
    
    Args:
        config: 向量存储配置
        
    Returns:
        配置好的VectorStore实例
    """
    # 兼容两种配置方式：type和provider
    store_type = config.get("provider", config.get("type", "chroma")).lower()
    
    if store_type == "chroma":
        return ChromaVectorStore(config)
    elif store_type == "qdrant":
        # 目前不支持Qdrant，暂时使用Chroma作为替代
        logger.warning("Qdrant向量存储尚未实现，将使用Chroma作为替代")
        return ChromaVectorStore(config)
    else:
        raise ValueError(f"不支持的向量存储类型: {store_type}") 