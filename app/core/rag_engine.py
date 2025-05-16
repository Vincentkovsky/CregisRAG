"""
RAG引擎 - 核心组件

这个模块实现了RAG（检索增强生成）的主要逻辑，包括:
1. 接收用户查询
2. 向量化查询
3. 从向量数据库检索相关文本
4. 构建LLM提示
5. 生成最终回答
"""
import logging
import time
import json
import os
from typing import List, Dict, Any, Optional, Tuple

# 导入核心组件
from app.core.embedding import EmbeddingService, create_embedding_service
from app.core.retrieval import VectorStore, create_vector_store
from app.core.generation import LLMService, create_llm_service
from app.core.ingest import TextChunker, DocumentProcessor, IngestService
from app.core.ingest import create_chunker_from_config, create_document_processor, create_ingest_service

# 配置日志
logger = logging.getLogger(__name__)

class RAGEngine:
    """
    RAG引擎类 - 检索增强生成系统的核心
    
    这个类整合了检索组件和生成组件，实现了完整的RAG流程。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化RAG引擎
        
        Args:
            config: 包含配置参数的字典
        """
        self.config = config
        
        # 初始化各个组件
        self.embedding_service = None
        self.vector_store = None
        self.llm_service = None
        self.ingest_service = None
        
        # 从配置加载参数
        self.retrieval_config = config.get("retrieval", {})
        self.top_k = self.retrieval_config.get("top_k", 5)
        self.similarity_threshold = self.retrieval_config.get("similarity_threshold", 0.7)
        self.use_reranking = self.retrieval_config.get("use_reranking", False)
        
        # 加载提示模板
        self.prompts = config.get("prompts", {})
        self.system_template = self.prompts.get("system_template", "")
        self.query_template = self.prompts.get("query_template", "")
        
        logger.info("RAG引擎初始化完成")
    
    async def initialize_services(self) -> bool:
        """
        初始化依赖的服务
        
        Returns:
            初始化是否成功
        """
        try:
            # 创建嵌入服务
            self.embedding_service = create_embedding_service(self.config.get("embedding", {}))
            if not await self.embedding_service.initialize():
                logger.error("嵌入服务初始化失败")
                return False
                
            # 创建向量存储
            self.vector_store = create_vector_store(self.config.get("vector_store", {}))
            if not await self.vector_store.initialize():
                logger.error("向量存储初始化失败")
                return False
                
            # 创建LLM服务
            self.llm_service = create_llm_service(self.config.get("llm", {}))
            if not await self.llm_service.initialize():
                logger.error("LLM服务初始化失败")
                return False
                
            # 创建文本分块器
            chunker = create_chunker_from_config(self.config.get("chunker", {}))
            
            # 创建文档处理器
            document_processor = create_document_processor(self.config.get("document_processor", {}))
            
            # 创建文档摄入服务
            self.ingest_service = create_ingest_service(
                document_processor=document_processor,
                chunker=chunker,
                embedding_service=self.embedding_service,
                vector_store=self.vector_store,
                config=self.config.get("ingest", {})
            )
            if not await self.ingest_service.initialize():
                logger.error("文档摄入服务初始化失败")
                return False
            
            logger.info("所有服务初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化服务时出错: {str(e)}")
            return False
    
    async def process_query(
        self, 
        query: str, 
        top_k: Optional[int] = None, 
        filter_metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理用户查询，执行完整的RAG流程
        
        Args:
            query: 用户查询
            top_k: 要检索的文档数量（如果为None，则使用默认值）
            filter_metadata: 用于过滤检索结果的元数据
            conversation_id: 可选的会话ID，用于跟踪会话上下文
            
        Returns:
            包含回答和源的字典
        """
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")
        
        # 确定top_k值
        if top_k is None:
            top_k = self.top_k
        
        try:
            # 1. 向量化查询
            if not self.embedding_service:
                raise ValueError("嵌入服务未初始化")
                
            query_vector = await self.embedding_service.embed_query(query)
            logger.debug("查询向量化完成")
            
            # 2. 检索相关文档
            if not self.vector_store:
                raise ValueError("向量存储未初始化")
                
            retrieved_docs = await self.vector_store.similarity_search(
                query_vector, 
                top_k=top_k,
                threshold=self.similarity_threshold,
                filter=filter_metadata
            )
            
            logger.debug(f"检索到 {len(retrieved_docs)} 个相关文档")
            
            # 3. 重新排序 (如果启用)
            if self.use_reranking and len(retrieved_docs) > 1:
                retrieved_docs = await self.rerank_documents(query, retrieved_docs)
                logger.debug("文档重排序完成")
            
            # 4. 构建提示
            context = self._build_context(retrieved_docs)
            prompt = self._build_prompt(query, context)
            
            # 5. 生成答案
            if not self.llm_service:
                raise ValueError("LLM服务未初始化")
                
            llm_response = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.system_template
            )
            
            answer = llm_response.get("text", "")
            logger.debug("LLM生成回答完成")
            
            # 准备源信息 - 使用文档名称而不是文件名
            # 创建一个集合用于跟踪已处理的文档名称，避免重复
            processed_docs = set()
            sources = []
            
            for doc in retrieved_docs:
                metadata = doc.get("metadata", {})
                # 优先使用filename作为文档名称，如果不存在则尝试使用file_name或title
                document_name = metadata.get("filename", 
                                          metadata.get("file_name", 
                                                    metadata.get("title", "未知文档")))
                
                # 如果这个文档名称已经处理过，跳过添加重复的来源
                if document_name in processed_docs:
                    continue
                
                # 添加到已处理集合
                processed_docs.add(document_name)
                
                # 准备源信息
                sources.append({
                    "document_id": doc.get("document_id", ""),
                    "document_name": document_name,
                    "text": doc.get("text", ""),
                    "score": doc.get("score", 0),
                    "metadata": metadata
                })
            
            # 记录查询和响应（可选）
            if conversation_id:
                self._save_interaction(conversation_id, query, answer, sources, llm_response)
            
            processing_time = time.time() - start_time
            logger.info(f"查询处理完成，耗时: {processing_time:.2f}秒")
            
            return {
                "query": query,
                "answer": answer,
                "sources": sources,
                "processing_time": processing_time,
                "model": llm_response.get("model", ""),
                "token_usage": llm_response.get("tokens", {})
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"处理查询时出错: {error_msg}")
            
            return {
                "query": query,
                "answer": f"处理查询时出错: {error_msg}",
                "sources": [],
                "processing_time": time.time() - start_time,
                "error": error_msg
            }
    
    def _build_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        从检索到的文档构建上下文字符串
        
        Args:
            documents: 检索到的文档列表
            
        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        
        for i, doc in enumerate(documents):
            metadata = doc.get("metadata", {})
            source = metadata.get("file_name", metadata.get("source", "未知文档"))
            page = metadata.get("page", "")
            page_info = f"，页码：{page}" if page else ""
            score = doc.get("score", 0)
            score_info = f"(相关度: {score:.2f})"
            
            context_parts.append(f"[文档{i+1}] {source}{page_info} {score_info}\n{doc.get('text', '')}\n")
        
        return "\n".join(context_parts)
    
    def _build_prompt(self, query: str, context: str) -> str:
        """
        构建发送给LLM的提示
        
        Args:
            query: 用户查询
            context: 从检索到的文档构建的上下文
            
        Returns:
            格式化的提示字符串
        """
        # 如果未设置查询模板，使用默认模板
        if not self.query_template:
            self.query_template = """
            以下是一些文档内容，请使用这些信息来回答用户的问题。
            如果文档中不包含足够的信息来回答问题，请说明你无法提供完整回答，并仅基于文档中的信息回答。
            不要编造信息。
            
            文档内容:
            {context}
            
            用户问题: {query}
            """
        
        # 替换查询模板中的占位符
        prompt = self.query_template.replace("{context}", context).replace("{query}", query)
        
        return prompt
    
    async def rerank_documents(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用交叉编码器重新排序检索到的文档
        
        实际实现中，这将使用更复杂的重排序逻辑或专用的重排序模型
        
        Args:
            query: 用户查询
            documents: 初始检索的文档
            
        Returns:
            重新排序的文档列表
        """
        # 在实际实现中，可以使用交叉编码器等模型进行重排序
        # 目前简单返回原始文档
        return documents
    
    async def ingest_document(self, 
                             file_path: str, 
                             metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入文档
        
        Args:
            file_path: 文件路径
            metadata: 可选的额外元数据
            
        Returns:
            摄入结果
        """
        if not self.ingest_service:
            raise ValueError("文档摄入服务未初始化")
            
        return await self.ingest_service.ingest_file(file_path, metadata)
    
    async def ingest_text(self, 
                         text: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        摄入文本
        
        Args:
            text: 文本内容
            metadata: 可选的元数据
            
        Returns:
            摄入结果
        """
        if not self.ingest_service:
            raise ValueError("文档摄入服务未初始化")
            
        return await self.ingest_service.ingest_text(text, metadata)
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        删除文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            删除结果
        """
        if not self.ingest_service:
            raise ValueError("文档摄入服务未初始化")
            
        return await self.ingest_service.delete_document(document_id)
    
    def _save_interaction(self, 
                         conversation_id: str, 
                         query: str, 
                         answer: str, 
                         sources: List[Dict[str, Any]],
                         llm_response: Dict[str, Any]) -> None:
        """保存查询和响应以供将来参考"""
        try:
            # 确保存储目录存在
            logs_dir = self.config.get("logs_dir", "./data/logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            # 创建交互记录
            interaction = {
                "timestamp": time.time(),
                "conversation_id": conversation_id,
                "query": query,
                "answer": answer,
                "sources": sources,
                "llm_info": {
                    "model": llm_response.get("model", ""),
                    "provider": llm_response.get("provider", ""),
                    "tokens": llm_response.get("tokens", {})
                }
            }
            
            # 保存为JSON文件
            file_path = os.path.join(logs_dir, f"interaction_{conversation_id}_{int(time.time())}.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(interaction, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存交互记录时出错: {str(e)}")


def create_rag_engine(config: Dict[str, Any]) -> RAGEngine:
    """
    从配置创建RAG引擎
    
    Args:
        config: 配置参数
        
    Returns:
        配置好的RAGEngine实例
    """
    return RAGEngine(config) 