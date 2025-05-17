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
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

# 导入核心组件
from app.core.embedding import EmbeddingService, create_embedding_service
from app.core.retrieval import VectorStore, create_vector_store
from app.core.generation import LLMService, create_llm_service
from app.core.ingest import TextChunker, DocumentProcessor, IngestService
from app.core.ingest import create_chunker_from_config, create_document_processor, create_ingest_service
from app.core.generation.llm_service import LLMService
from app.core.storage.storage_service import StorageService
from app.core.ingest.document_processor import Document, DocumentChunk

# 导入日志处理工具
from app.utils.log_handler import record_query, record_error

# 配置日志
logger = logging.getLogger(__name__)

class RAGEngine:
    """
    RAG引擎类 - 检索增强生成系统的核心
    
    这个类整合了检索组件和生成组件，实现了完整的RAG流程。
    """
    
    def __init__(self, config: Dict[str, Any], llm_service: LLMService, 
                 embedding_service: EmbeddingService, storage_service: StorageService):
        """
        初始化RAG引擎
        
        Args:
            config: 包含配置参数的字典
            llm_service: 大语言模型服务
            embedding_service: 嵌入服务
            storage_service: 存储服务
        """
        self.config = config
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.storage_service = storage_service
        
        # 初始化各个组件
        self.vector_store = None
        self.ingest_service = None
        
        # 从配置加载参数
        self.retrieval_config = config.get("retrieval", {})
        self.top_k = self.retrieval_config.get("top_k", 5)
        self.similarity_threshold = self.retrieval_config.get("similarity_threshold", 0.3)
        self.use_reranking = self.retrieval_config.get("use_reranking", True)
        
        # 混合检索配置
        self.enable_hybrid_search = config.get("enable_hybrid_search", True)
        self.hybrid_search_weight = config.get("hybrid_search_weight", 0.3)  # BM25权重，余弦相似度权重为(1-hybrid_search_weight)
        
        # MMR配置（最大边际相关性）- 用于增加检索多样性
        self.use_mmr = config.get("use_mmr", False)
        self.mmr_lambda = config.get("mmr_lambda", 0.5)
        
        # 检测语言并自动调整检索策略
        self.auto_detect_language = config.get("auto_detect_language", True)
        
        # 加载提示模板
        self.prompts = config.get("prompts", {})
        self.system_template = self.prompts.get("system_template", "")
        self.query_template = self.prompts.get("query_template", "")
        
        # 生成配置
        self.prompt_template = config.get("prompt_template", 
            """
            你是一个AI助手，根据以下参考文档回答问题。
            如果参考文档中没有包含问题的答案，请说明您无法回答这个问题。
            请不要编造任何不在参考文档中的信息。
            
            参考文档:
            {{documents}}
            
            问题: {{query}}
            
            回答:
            """
        )
        self.max_document_length = config.get("max_document_length", 8000)
        
        logger.info("RAG引擎初始化完成")
    
    async def initialize_services(self) -> bool:
        """
        初始化依赖的服务
        
        Returns:
            初始化是否成功
        """
        try:
            # 检查并确保LLM服务已初始化
            if self.llm_service is None:
                logger.error("LLM服务未提供，无法初始化RAG引擎")
                return False
                
            # 检查并确保嵌入服务已初始化
            if self.embedding_service is None:
                logger.error("嵌入服务未提供，无法初始化RAG引擎")
                return False
                
            # 检查并确保存储服务已初始化
            if self.storage_service is None:
                logger.error("存储服务未提供，无法初始化RAG引擎")
                return False
                
            # 确保LLM服务已初始化
            logger.info("确保LLM服务已初始化...")
            if not await self.llm_service.initialize():
                logger.error("LLM服务初始化失败")
                return False
                
            # 确保嵌入服务已初始化
            logger.info("确保嵌入服务已初始化...")
            if not await self.embedding_service.initialize():
                logger.error("嵌入服务初始化失败")
                return False
                
            # 创建向量存储
            self.vector_store = create_vector_store(self.config.get("vector_store", {}))
            if not await self.vector_store.initialize():
                logger.error("向量存储初始化失败")
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
                
            # 使用一个较低的阈值以确保能够检索到相关文档
            hard_coded_threshold = 0.0  # 暂时硬编码一个极低的阈值
            retrieved_docs, retrieval_time = await self._retrieve_documents(query, filter_metadata)
            
            logger.debug(f"检索到 {len(retrieved_docs)} 个相关文档")
            
            # 3. 重新排序 (如果启用) - 注意：检索方法现在返回DocumentChunk对象，无需使用_rerank_results
            # 我们可以直接按相似度排序
            if self.use_reranking and len(retrieved_docs) > 1:
                logger.debug("开始文档重排序")
                # 确保按相似度排序
                retrieved_docs = sorted(retrieved_docs, key=lambda x: x.similarity, reverse=True)
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
                # 直接访问DocumentChunk对象的属性
                metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                
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
                document_id = doc.document_id if hasattr(doc, 'document_id') else ""
                content = doc.content if hasattr(doc, 'content') else ""
                similarity = doc.similarity if hasattr(doc, 'similarity') else 0.0
                
                sources.append({
                    "document_id": document_id,
                    "document_name": document_name,
                    "text": content,
                    "score": similarity,
                    "metadata": metadata
                })
            
            # 记录查询和响应（可选）
            if conversation_id:
                self._save_interaction(conversation_id, query, answer, sources, llm_response)
            
            processing_time = time.time() - start_time
            logger.info(f"查询处理完成，耗时: {processing_time:.2f}秒")
            
            # 使用日志处理器记录成功的查询
            token_usage = llm_response.get("tokens", {})
            record_query(
                query=query,
                answer=answer,
                sources=sources,
                processing_time=processing_time,
                token_usage=token_usage
            )
            
            return {
                "query": query,
                "answer": answer,
                "sources": sources,
                "processing_time": processing_time,
                "model": llm_response.get("model", ""),
                "token_usage": token_usage
            }
            
        except Exception as e:
            error_msg = str(e)
            processing_time = time.time() - start_time
            logger.error(f"处理查询时出错: {error_msg}")
            
            # 使用日志处理器记录错误
            record_error(
                error_type="rag_processing_error",
                message=error_msg,
                component="rag_engine",
                details={
                    "query": query,
                    "processing_time": processing_time,
                    "conversation_id": conversation_id,
                    "filter_metadata": filter_metadata
                }
            )
            
            return {
                "query": query,
                "answer": f"处理查询时出错: {error_msg}",
                "sources": [],
                "processing_time": processing_time,
                "error": error_msg
            }
    
    def _build_context(self, documents: List[DocumentChunk]) -> str:
        """
        从检索到的文档构建上下文字符串
        
        Args:
            documents: 检索到的文档列表
            
        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        
        for i, doc in enumerate(documents):
            # 直接访问DocumentChunk的属性
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            content = doc.content if hasattr(doc, 'content') else ""
            similarity = doc.similarity if hasattr(doc, 'similarity') else 0.0
            
            # 从元数据中获取文档来源信息
            source = metadata.get("file_name", metadata.get("source", metadata.get("filename", "未知文档")))
            page = metadata.get("page", "")
            page_info = f"，页码：{page}" if page else ""
            score_info = f"(相关度: {similarity:.2f})"
            
            context_parts.append(f"[文档{i+1}] {source}{page_info} {score_info}\n{content}\n")
        
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
    
    async def _retrieve_documents(self, query: str, metadata_filter: Optional[Dict[str, Any]] = None) -> Tuple[List[DocumentChunk], float]:
        """
        检索与查询相关的文档
        
        Args:
            query: 用户查询
            metadata_filter: 文档元数据过滤条件
            
        Returns:
            相关文档列表和检索时间
        """
        start_time = time.time()
        logger.info(f"开始检索文档: {query}")
        
        try:
            # 检查必要的服务是否可用
            if self.embedding_service is None:
                logger.error("嵌入服务未初始化，无法检索文档")
                return [], time.time() - start_time
                
            if self.storage_service is None:
                logger.error("存储服务未初始化，无法检索文档")
                return [], time.time() - start_time
                
            # 获取查询的嵌入
            try:
                query_embedding = await self.embedding_service.embed_query(query)
            except Exception as e:
                logger.error(f"嵌入查询失败: {str(e)}")
                return [], time.time() - start_time
            
            # 确定检索参数
            similarity_threshold = 0.0 if self.similarity_threshold is None else self.similarity_threshold
            
            # 选择检索方法
            results = []
            if self.enable_hybrid_search:
                try:
                    # 使用混合检索 (向量检索 + 关键词检索)
                    results = await self.storage_service.hybrid_search(
                        query=query,
                        query_embedding=query_embedding,
                        limit=self.top_k * 2,  # 检索更多候选，后续重排序
                        metadata_filter=metadata_filter,
                        hybrid_weight=self.hybrid_search_weight
                    )
                except Exception as e:
                    logger.error(f"混合搜索失败: {str(e)}")
                    # 如果混合搜索失败，尝试回退到纯向量搜索
                    try:
                        results = await self.storage_service.vector_search(
                            query_embedding=query_embedding,
                            limit=self.top_k * 2,
                            metadata_filter=metadata_filter
                        )
                    except Exception as e2:
                        logger.error(f"向量搜索也失败: {str(e2)}")
                        return [], time.time() - start_time
            else:
                try:
                    # 使用纯向量检索
                    results = await self.storage_service.vector_search(
                        query_embedding=query_embedding,
                        limit=self.top_k * 2,
                        metadata_filter=metadata_filter
                    )
                except Exception as e:
                    logger.error(f"向量搜索失败: {str(e)}")
                    return [], time.time() - start_time
            
            # 应用相似度阈值过滤
            filtered_results = []
            for result in results:
                # 检查相似度是否超过阈值
                if result.get("similarity", 0) >= similarity_threshold:
                    filtered_results.append(result)
            
            # 如果启用了重排序，则对结果进行重排序
            if self.use_reranking and len(filtered_results) > 1:
                try:
                    filtered_results = await self._rerank_results(query, filtered_results)
                except Exception as e:
                    logger.error(f"重排序失败: {str(e)}")
                    # 重排序失败不影响继续使用已有结果
            
            # 选择前K个结果
            top_results = filtered_results[:self.top_k]
            
            # 将结果转换为DocumentChunk对象
            retrieved_docs = []
            for result in top_results:
                try:
                    # 获取文档ID - 使用document_id或id
                    chunk_id = result.get("id", "")
                    
                    if not chunk_id:
                        logger.warning(f"检索结果缺少ID字段: {result}")
                        continue
                    
                    # 如果结果中已经包含文本内容，直接使用
                    # 同时支持content和text字段
                    if "text" in result:
                        content = result["text"]
                        metadata = result.get("metadata", {})
                        similarity = result.get("similarity", 0)
                        document_id = metadata.get("document_id", "")
                        
                        doc_chunk = DocumentChunk(
                            id=chunk_id,
                            document_id=document_id,
                            content=content,
                            metadata=metadata,
                            similarity=similarity
                        )
                        retrieved_docs.append(doc_chunk)
                    else:
                        # 否则，从存储中获取文档片段
                        doc_chunk = await self.storage_service.get_document_chunk(chunk_id)
                        if doc_chunk:
                            # 添加相似度得分
                            doc_chunk.similarity = result.get("similarity", 0)
                            retrieved_docs.append(doc_chunk)
                        else:
                            logger.warning(f"无法从存储中检索文档片段: {chunk_id}")
                except Exception as e:
                    logger.error(f"处理检索结果时出错: {str(e)}, 结果: {result}")
                    # 继续处理其他结果
                    continue
            
            retrieval_time = time.time() - start_time
            logger.info(f"检索完成: 找到 {len(retrieved_docs)} 个文档片段, 耗时: {retrieval_time:.2f}秒")
            
            return retrieved_docs, retrieval_time
            
        except Exception as e:
            retrieval_time = time.time() - start_time
            logger.error(f"检索文档时发生错误: {str(e)}")
            return [], retrieval_time
    
    async def _rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重排序检索结果
        
        Args:
            query: 用户查询
            results: 初始检索结果
            
        Returns:
            重排序后的结果
        """
        if not results:
            logger.debug("无检索结果，跳过重排序")
            return []
            
        # 如果使用MMR（最大边际相关性），进行多样性重排序
        if self.use_mmr:
            return self._apply_mmr(query, results)
        
        # 目前仅支持直接使用相似度得分重排序
        # 未来可以添加更高级的重排序方法，如基于交叉编码器的重排序
        return sorted(results, key=lambda x: x["similarity"] if "similarity" in x else 0, reverse=True)
    
    def _apply_mmr(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        应用最大边际相关性算法进行多样性重排序
        
        Args:
            query: 用户查询
            results: 初始检索结果
            
        Returns:
            MMR重排序后的结果
        """
        if not results:
            return []
            
        # 提取文档嵌入向量和分数
        vectors = []
        for result in results:
            if "vector" in result:
                vectors.append(np.array(result["vector"]))
            else:
                # 如果结果中没有向量，需要重新嵌入或跳过MMR
                logger.warning("结果中没有嵌入向量，无法应用MMR")
                return sorted(results, key=lambda x: x["similarity"] if "similarity" in x else 0, reverse=True)
        
        # MMR参数
        lambda_param = self.mmr_lambda  # 相关性和多样性的平衡参数
        
        # 已选择和候选文档索引
        selected_indices = []
        candidate_indices = list(range(len(results)))
        
        # 按MMR选择文档，直到选够所有文档
        while len(selected_indices) < len(results):
            best_score = -1
            best_idx = -1
            
            for cand_idx in candidate_indices:
                # 计算与查询的相关性得分
                relevance = results[cand_idx]["similarity"] if "similarity" in results[cand_idx] else 0
                
                # 计算与已选文档的最大相似度
                max_similarity = 0
                if selected_indices:
                    for sel_idx in selected_indices:
                        similarity = self._cosine_similarity(vectors[cand_idx], vectors[sel_idx])
                        max_similarity = max(max_similarity, similarity)
                
                # 计算MMR得分
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = cand_idx
            
            if best_idx == -1:
                break
                
            selected_indices.append(best_idx)
            candidate_indices.remove(best_idx)
        
        # 按照MMR排序返回结果
        return [results[idx] for idx in selected_indices]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0
            
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    async def _generate_answer(self, query: str, retrieved_docs: List[DocumentChunk]) -> str:
        """
        生成查询的答案
        
        Args:
            query: 用户查询
            retrieved_docs: 检索到的文档片段
            
        Returns:
            生成的答案
        """
        try:
            # 准备上下文文本
            context_text = self._prepare_context(retrieved_docs)
            
            # 使用提示模板
            prompt = self.prompt_template.replace("{{query}}", query).replace("{{documents}}", context_text)
            
            # 使用LLM生成答案
            answer = await self.llm_service.generate_text(prompt, temperature=0.3)
            
            return answer
            
        except Exception as e:
            logger.error(f"生成答案时出错: {str(e)}")
            return "抱歉，在处理您的问题时出现了错误。"
    
    def _prepare_context(self, retrieved_docs: List[DocumentChunk]) -> str:
        """
        准备用于LLM上下文的文本
        
        Args:
            retrieved_docs: 检索到的文档片段
            
        Returns:
            合并后的上下文文本
        """
        # 按相似度排序
        sorted_docs = sorted(retrieved_docs, key=lambda x: getattr(x, "similarity", 0), reverse=True)
        
        # 合并文档片段
        context_parts = []
        current_length = 0
        
        for doc in sorted_docs:
            # 提取文档内容
            content = doc.content
            
            # 添加文档元数据（可选）
            if hasattr(doc, "metadata") and doc.metadata:
                doc_source = doc.metadata.get("source", "")
                if doc_source:
                    content = f"来源: {doc_source}\n\n{content}"
            
            # 检查是否会超过最大长度
            if current_length + len(content) + 2 > self.max_document_length:
                # 如果已经有内容，可以停止添加
                if context_parts:
                    break
                # 否则，可以截断当前文档
                available_space = self.max_document_length - current_length - 2
                if available_space > 100:  # 至少保留100个字符
                    content = content[:available_space] + "..."
            
            # 添加文档内容
            context_parts.append(content)
            current_length += len(content) + 2  # +2 为分隔符长度
        
        # 使用分隔符合并文档
        context_text = "\n\n---\n\n".join(context_parts)
        
        return context_text
    
    def _prepare_sources(self, retrieved_docs: List[DocumentChunk]) -> List[Dict[str, Any]]:
        """
        准备结果中的来源信息
        
        Args:
            retrieved_docs: 检索到的文档片段
            
        Returns:
            包含来源信息的字典列表
        """
        sources = []
        
        for doc in retrieved_docs:
            source_info = {
                "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "similarity": getattr(doc, "similarity", 0)
            }
            
            # 添加元数据
            if hasattr(doc, "metadata") and doc.metadata:
                source_info["metadata"] = doc.metadata
            
            sources.append(source_info)
        
        return sources
    
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


def create_rag_engine(config: Dict[str, Any], llm_service=None, embedding_service=None, storage_service=None) -> RAGEngine:
    """
    从配置创建RAG引擎
    
    Args:
        config: 配置参数
        llm_service: 大语言模型服务
        embedding_service: 嵌入服务
        storage_service: 存储服务
        
    Returns:
        配置好的RAGEngine实例
    """
    # 如果未提供服务实例，可以在此创建默认服务
    if llm_service is None:
        from app.core.generation import create_llm_service
        llm_service = create_llm_service(config.get("llm", {}))
    
    if embedding_service is None:
        from app.core.embedding import create_embedding_service
        embedding_service = create_embedding_service(config.get("embedding", {}))
    
    if storage_service is None:
        from app.core.storage.storage_service import create_storage_service
        storage_service = create_storage_service(config.get("storage", {}))
    
    return RAGEngine(
        config=config,
        llm_service=llm_service,
        embedding_service=embedding_service,
        storage_service=storage_service
    ) 