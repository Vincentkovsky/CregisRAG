"""
文档摄入服务模块

该模块整合了文档处理、分块和向量化流程，提供端到端的文档摄入功能。
"""
import os
import logging
import time
import json
import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
import numpy as np

# 配置日志
logger = logging.getLogger(__name__)

class IngestService:
    """
    文档摄入服务类
    
    协调文档处理、分块和向量化的整个过程。
    """
    
    def __init__(self, 
                document_processor=None, 
                chunker=None, 
                embedding_service=None, 
                vector_store=None,
                config: Dict[str, Any] = None):
        """
        初始化摄入服务
        
        Args:
            document_processor: 文档处理器实例
            chunker: 文本分块器实例
            embedding_service: 嵌入服务实例
            vector_store: 向量存储实例
            config: 配置参数
        """
        self.document_processor = document_processor
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.config = config or {}
        
        # 从配置读取参数
        self.source_dir = self.config.get("source_dir", "./data/raw")
        self.processed_dir = self.config.get("processed_dir", "./data/processed")
        self.save_processed = self.config.get("save_processed", True)
        self.batch_size = self.config.get("batch_size", 10)
        
        # 确保目录存在
        if self.save_processed:
            os.makedirs(self.processed_dir, exist_ok=True)
        
        logger.info("初始化文档摄入服务")
    
    async def initialize(self) -> bool:
        """
        初始化摄入服务组件
        
        Returns:
            初始化是否成功
        """
        try:
            # 初始化依赖服务
            init_tasks = []
            
            if self.document_processor:
                init_tasks.append(asyncio.sleep(0))  # 文档处理器不需要异步初始化
                
            if self.chunker:
                init_tasks.append(asyncio.sleep(0))  # 分块器不需要异步初始化
                
            if self.embedding_service:
                init_tasks.append(self.embedding_service.initialize())
                
            if self.vector_store:
                init_tasks.append(self.vector_store.initialize())
            
            # 等待所有初始化完成
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            
            # 检查是否有初始化失败
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"初始化组件时出错: {str(result)}")
                    return False
                elif result is False:
                    logger.error("一个或多个组件初始化失败")
                    return False
            
            logger.info("文档摄入服务初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化文档摄入服务时出错: {str(e)}")
            return False
    
    async def ingest_file(self, 
                         file_path: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入单个文件
        
        Args:
            file_path: 文件路径
            metadata: 可选的额外元数据
            
        Returns:
            包含处理结果的字典
        """
        start_time = time.time()
        document_id = str(uuid.uuid4())
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
                
            if not self.document_processor:
                raise ValueError("文档处理器未初始化")
                
            logger.info(f"开始摄入文件: {file_path}")
            
            # 1. 处理文档
            document_result = await self.document_processor.process_file(file_path)
            
            if "error" in document_result:
                logger.error(f"处理文档时出错: {document_result['error']}")
                return {
                    "document_id": document_id,
                    "status": "failed",
                    "error": document_result["error"],
                    "file_path": file_path
                }
            
            # 合并元数据
            if metadata:
                document_result["metadata"].update(metadata)
            
            # 添加文档ID
            document_result["metadata"]["document_id"] = document_id
            
            # 2. 文本分块
            if not self.chunker:
                logger.warning("分块器未初始化，将跳过分块步骤")
                chunks = [{
                    "text": document_result["text"],
                    "metadata": document_result["metadata"]
                }]
            else:
                chunks = self.chunker.chunk_text(
                    document_result["text"], 
                    document_result["metadata"]
                )
                logger.info(f"文档被分成 {len(chunks)} 个块")
            
            # 3. 向量化和存储
            if self.embedding_service and self.vector_store:
                # 提取文本列表用于向量化
                texts = [chunk["text"] for chunk in chunks]
                
                # 批量处理，避免一次性处理太多文本
                chunk_ids = []
                
                for i in range(0, len(chunks), self.batch_size):
                    batch_chunks = chunks[i:i + self.batch_size]
                    batch_texts = texts[i:i + self.batch_size]
                    
                    # 向量化
                    embeddings = await self.embedding_service.embed_texts(batch_texts)
                    
                    # 存储到向量数据库
                    batch_ids = await self.vector_store.add_documents(batch_chunks, embeddings)
                    chunk_ids.extend(batch_ids)
                
                logger.info(f"已向量化并存储 {len(chunk_ids)} 个文本块")
            else:
                logger.warning("嵌入服务或向量存储未初始化，将跳过向量化步骤")
                chunk_ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            # 4. 保存处理后的文档（可选）
            if self.save_processed:
                await self._save_processed_document(document_id, document_result, chunks)
            
            processing_time = time.time() - start_time
            logger.info(f"文件摄入完成: {file_path}, 耗时: {processing_time:.2f}秒")
            
            return {
                "document_id": document_id,
                "status": "success",
                "file_path": file_path,
                "chunk_count": len(chunks),
                "chunk_ids": chunk_ids,
                "processing_time": processing_time
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"摄入文件时出错: {error_msg}")
            
            return {
                "document_id": document_id,
                "status": "failed",
                "error": error_msg,
                "file_path": file_path
            }
    
    async def ingest_text(self, 
                         text: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入原始文本
        
        Args:
            text: 要摄入的文本
            metadata: 文本的元数据
            
        Returns:
            包含处理结果的字典
        """
        start_time = time.time()
        document_id = str(uuid.uuid4())
        
        try:
            if not self.document_processor:
                raise ValueError("文档处理器未初始化")
                
            logger.info(f"开始摄入文本: 长度={len(text)}")
            
            # 1. 处理文本
            if metadata is None:
                metadata = {}
            
            # 添加文档ID
            metadata["document_id"] = document_id
            metadata["source_type"] = "text"
            
            document_result = await self.document_processor.process_text(text, metadata)
            
            # 2. 文本分块
            if not self.chunker:
                logger.warning("分块器未初始化，将跳过分块步骤")
                chunks = [{
                    "text": document_result["text"],
                    "metadata": document_result["metadata"]
                }]
            else:
                chunks = self.chunker.chunk_text(
                    document_result["text"], 
                    document_result["metadata"]
                )
                logger.info(f"文本被分成 {len(chunks)} 个块")
            
            # 3. 向量化和存储
            if self.embedding_service and self.vector_store:
                # 提取文本列表用于向量化
                texts = [chunk["text"] for chunk in chunks]
                
                # 批量处理
                chunk_ids = []
                
                for i in range(0, len(chunks), self.batch_size):
                    batch_chunks = chunks[i:i + self.batch_size]
                    batch_texts = texts[i:i + self.batch_size]
                    
                    # 向量化
                    embeddings = await self.embedding_service.embed_texts(batch_texts)
                    
                    # 存储到向量数据库
                    batch_ids = await self.vector_store.add_documents(batch_chunks, embeddings)
                    chunk_ids.extend(batch_ids)
                
                logger.info(f"已向量化并存储 {len(chunk_ids)} 个文本块")
            else:
                logger.warning("嵌入服务或向量存储未初始化，将跳过向量化步骤")
                chunk_ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            # 4. 保存处理后的文档（可选）
            if self.save_processed:
                await self._save_processed_document(document_id, document_result, chunks)
            
            processing_time = time.time() - start_time
            logger.info(f"文本摄入完成, 耗时: {processing_time:.2f}秒")
            
            return {
                "document_id": document_id,
                "status": "success",
                "chunk_count": len(chunks),
                "chunk_ids": chunk_ids,
                "processing_time": processing_time
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"摄入文本时出错: {error_msg}")
            
            return {
                "document_id": document_id,
                "status": "failed",
                "error": error_msg
            }
    
    async def ingest_directory(self, 
                              directory_path: str, 
                              recursive: bool = True,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入整个目录中的文件
        
        Args:
            directory_path: 目录路径
            recursive: 是否递归处理子目录
            metadata: 应用于所有文件的基础元数据
            
        Returns:
            包含处理结果的字典
        """
        start_time = time.time()
        
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                raise ValueError(f"目录不存在或不是目录: {directory_path}")
                
            logger.info(f"开始摄入目录: {directory_path}")
            
            # 收集文件
            file_paths = []
            
            if recursive:
                # 递归遍历目录
                for root, _, files in os.walk(directory_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_paths.append(file_path)
            else:
                # 只处理当前目录中的文件
                for item in os.listdir(directory_path):
                    item_path = os.path.join(directory_path, item)
                    if os.path.isfile(item_path):
                        file_paths.append(item_path)
            
            logger.info(f"发现 {len(file_paths)} 个文件")
            
            # 处理每个文件
            results = []
            
            for file_path in file_paths:
                # 创建文件特定的元数据
                file_metadata = metadata.copy() if metadata else {}
                file_metadata["source_directory"] = directory_path
                
                # 摄入文件
                result = await self.ingest_file(file_path, file_metadata)
                results.append(result)
            
            # 汇总结果
            success_count = sum(1 for r in results if r["status"] == "success")
            failed_count = len(results) - success_count
            
            processing_time = time.time() - start_time
            logger.info(f"目录摄入完成: {directory_path}, 处理了 {len(results)} 个文件, 成功: {success_count}, 失败: {failed_count}, 总耗时: {processing_time:.2f}秒")
            
            return {
                "status": "completed",
                "directory": directory_path,
                "total_files": len(results),
                "successful_files": success_count,
                "failed_files": failed_count,
                "results": results,
                "processing_time": processing_time
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"摄入目录时出错: {error_msg}")
            
            return {
                "status": "failed",
                "directory": directory_path,
                "error": error_msg
            }
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        从系统中删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            包含操作结果的字典
        """
        try:
            if not self.vector_store:
                raise ValueError("向量存储未初始化")
                
            logger.info(f"开始删除文档: {document_id}")
            
            # 获取所有文档
            all_documents = await self.vector_store.get_all_documents_metadata()
            if not all_documents:
                logger.warning(f"向量存储中没有找到任何文档")
                return {
                    "status": "success",
                    "document_id": document_id,
                    "deleted_chunks": 0,
                    "message": "向量存储中没有找到任何文档"
                }
            
            # 查找所有与当前文档ID相关的块
            # 场景1: 块的document_id直接等于document_id
            # 场景2: 块的document_id格式为 doc_{document_id}_{index}
            # 场景3: 块的原始document_id存储在元数据中
            chunks_to_delete = []
            for doc in all_documents:
                doc_id = doc.get("document_id", "")
                # 场景1: 直接匹配
                if doc_id == document_id:
                    chunks_to_delete.append(doc_id)
                    continue
                    
                # 场景2: 格式为 doc_{document_id}_{index}
                if doc_id.startswith(f"doc_{document_id}_") or doc_id.startswith(f"{document_id}_"):
                    chunks_to_delete.append(doc_id)
                    continue
                    
                # 场景3: 检查元数据中的original_document_id
                if doc.get("original_document_id") == document_id:
                    chunks_to_delete.append(doc_id)
                    continue
                    
                # 检查文件路径中是否包含文档ID
                file_path = doc.get("file_path", "")
                if document_id in file_path:
                    chunks_to_delete.append(doc_id)
                    continue
            
            if not chunks_to_delete:
                # 如果上述方法未找到文档，尝试使用相似度搜索作为备用方法
                logger.warning(f"通过ID匹配未找到文档，尝试使用相似度搜索作为备选方法")
                
                # 查找所有属于该文档的块
                filter = {"document_id": document_id}
                
                # 创建一个虚拟查询向量（全为0）
                query_vector = np.zeros(self.vector_store.embedding_dimension)
                
                # 检索所有相关块
                search_chunks = await self.vector_store.similarity_search(
                    query_vector,
                    top_k=1000,  # 设置较大的值以获取所有块
                    filter=filter
                )
                
                if search_chunks:
                    # 提取块ID
                    chunks_to_delete = [chunk["document_id"] for chunk in search_chunks]
            
            if not chunks_to_delete:
                logger.warning(f"未找到属于文档 {document_id} 的块")
                return {
                    "status": "success",
                    "document_id": document_id,
                    "deleted_chunks": 0,
                    "message": "未找到文档块"
                }
            
            logger.info(f"找到 {len(chunks_to_delete)} 个需要删除的文档块: {chunks_to_delete}")
            
            # 从向量存储中删除
            success = await self.vector_store.delete_documents(chunks_to_delete)
            
            if not success:
                raise ValueError("从向量存储删除文档失败")
                
            # 删除处理后的文件（如果存在）
            processed_path = os.path.join(self.processed_dir, f"{document_id}.json")
            if os.path.exists(processed_path):
                os.remove(processed_path)
                
            logger.info(f"文档删除成功: {document_id}, 删除了 {len(chunks_to_delete)} 个块")
            
            return {
                "status": "success",
                "document_id": document_id,
                "deleted_chunks": len(chunks_to_delete)
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"删除文档时出错: {error_msg}")
            
            return {
                "status": "failed",
                "document_id": document_id,
                "error": error_msg
            }
    
    async def _save_processed_document(self, 
                                      document_id: str, 
                                      document: Dict[str, Any], 
                                      chunks: List[Dict[str, Any]]) -> None:
        """保存处理后的文档和块"""
        try:
            # 创建包含文档和块的数据结构
            data = {
                "document_id": document_id,
                "metadata": document["metadata"],
                "text_length": len(document["text"]),
                "chunks": chunks,
                "processed_time": time.time()
            }
            
            # 保存为JSON文件
            output_path = os.path.join(self.processed_dir, f"{document_id}.json")
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"已保存处理后的文档: {output_path}")
            
        except Exception as e:
            logger.error(f"保存处理后的文档时出错: {str(e)}")


def create_ingest_service(
    document_processor, 
    chunker, 
    embedding_service, 
    vector_store,
    config: Dict[str, Any] = None
) -> IngestService:
    """
    创建文档摄入服务
    
    Args:
        document_processor: 文档处理器
        chunker: 文本分块器
        embedding_service: 嵌入服务
        vector_store: 向量存储
        config: 配置参数
        
    Returns:
        配置好的IngestService实例
    """
    return IngestService(
        document_processor=document_processor,
        chunker=chunker,
        embedding_service=embedding_service,
        vector_store=vector_store,
        config=config
    ) 