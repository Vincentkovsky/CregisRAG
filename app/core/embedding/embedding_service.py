"""
嵌入服务模块

该模块提供文本嵌入功能，用于将文本转换为向量表示。
支持多种嵌入模型和提供商。
"""
import logging
import time
import os
import re
from typing import List, Dict, Any, Optional, Union
import numpy as np

# 配置日志
logger = logging.getLogger(__name__)

def replace_env_vars(value: str) -> str:
    """替换字符串中的环境变量引用"""
    if not isinstance(value, str):
        return value
        
    # 使用正则表达式匹配 ${...} 模式
    pattern = r'\${([A-Za-z0-9_]+)}'
    
    def replace_env_var(match):
        env_var_name = match.group(1)
        env_var_value = os.environ.get(env_var_name)
        if env_var_value is None:
            logger.warning(f"环境变量 {env_var_name} 未定义")
            return match.group(0)  # 如果未定义则保持原样
        return env_var_value
    
    return re.sub(pattern, replace_env_var, value)

class EmbeddingService:
    """
    嵌入服务类
    
    将文本转换为向量表示。支持多种嵌入模型和API。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化嵌入服务
        
        Args:
            config: 包含配置参数的字典
        """
        self.config = config.copy()  # 创建配置的副本，以便可以修改
        
        # 处理config中的环境变量引用
        if "api_key" in self.config and isinstance(self.config["api_key"], str):
            self.config["api_key"] = replace_env_vars(self.config["api_key"])
        
        # 获取配置参数
        self.provider = self.config.get("provider", "openai").lower()
        self.model_name = self.config.get("model", self.config.get("model_name", "text-embedding-ada-002"))
        self.dimension = self.config.get("dimension", self.config.get("dimensions", 1536))  # 默认OpenAI ada-002嵌入维度
        self.batch_size = self.config.get("batch_size", 8)
        self.cache_enabled = self.config.get("cache_enabled", True)
        
        # 嵌入缓存
        self._cache = {} if self.cache_enabled else None
        
        # 嵌入客户端
        self.client = None
        
        logger.info(f"初始化嵌入服务: 提供商={self.provider}, 模型={self.model_name}")
    
    async def initialize(self) -> bool:
        """
        初始化嵌入客户端
        
        Returns:
            初始化是否成功
        """
        try:
            if self.provider == "openai":
                from openai import AsyncOpenAI
                
                api_key = self.config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
                api_base = self.config.get("api_base")
                
                if not api_key:
                    raise ValueError("使用OpenAI嵌入服务需要API密钥")
                
                self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
            
            elif self.provider == "huggingface":
                # 这里可以添加HuggingFace嵌入支持
                pass
            
            elif self.provider == "local":
                # 这里可以添加本地嵌入模型支持，如使用sentence-transformers
                try:
                    from sentence_transformers import SentenceTransformer
                    model_path = self.config.get("model_path", self.model_name)
                    self.client = SentenceTransformer(model_path)
                except ImportError:
                    logger.error("使用本地嵌入需要安装sentence-transformers库")
                    return False
            
            elif self.provider == "deepseek":
                # DeepSeek通常使用OpenAI兼容API
                from openai import AsyncOpenAI
                
                api_key = self.config.get("api_key", os.environ.get("DEEPSEEK_API_KEY", ""))
                api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
                
                if not api_key:
                    raise ValueError("使用DeepSeek嵌入服务需要API密钥")
                
                self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
                logger.info(f"初始化DeepSeek嵌入服务，模型: {self.model_name}")
            
            elif self.provider == "zhipuai":
                # 使用ZhipuAI的嵌入服务
                try:
                    from zhipuai import ZhipuAI
                    
                    api_key = self.config.get("api_key", os.environ.get("ZHIPUAI_API_KEY", ""))
                    
                    if not api_key:
                        raise ValueError("使用智谱AI嵌入服务需要API密钥")
                    
                    logger.info("已获取智谱AI API密钥")
                    self.client = ZhipuAI(api_key=api_key)
                    logger.info(f"初始化智谱AI嵌入服务，模型: {self.model_name}")
                except ImportError:
                    logger.error("使用智谱AI嵌入需要安装zhipuai库，请使用pip install zhipuai安装")
                    return False
            
            else:
                raise ValueError(f"不支持的嵌入提供商: {self.provider}")
            
            logger.info(f"嵌入服务初始化成功: {self.provider}")
            return True
            
        except Exception as e:
            logger.error(f"嵌入服务初始化失败: {str(e)}")
            return False
    
    async def embed_text(self, text: str) -> np.ndarray:
        """
        嵌入单个文本
        
        Args:
            text: 要嵌入的文本
            
        Returns:
            文本的向量表示
        """
        result = await self.embed_texts([text])
        return result[0]
    
    async def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        批量嵌入多个文本
        
        Args:
            texts: 要嵌入的文本列表
            
        Returns:
            向量表示列表
        """
        if not texts:
            logger.warning("收到空文本列表进行嵌入")
            return []
        
        # 检查缓存
        if self.cache_enabled:
            cache_hits = []
            texts_to_embed = []
            
            for text in texts:
                if text in self._cache:
                    cache_hits.append(self._cache[text])
                else:
                    cache_hits.append(None)
                    texts_to_embed.append(text)
                    
            # 如果全部命中缓存，返回缓存结果
            if not texts_to_embed:
                return [hit for hit in cache_hits if hit is not None]
        else:
            texts_to_embed = texts
            cache_hits = [None] * len(texts)
        
        # 根据提供商调用嵌入API
        start_time = time.time()
        embeddings = []
        
        try:
            if self.provider == "openai":
                embeddings = await self._embed_with_openai(texts_to_embed)
            elif self.provider == "deepseek":
                embeddings = await self._embed_with_openai(texts_to_embed)  # DeepSeek使用OpenAI兼容API
            elif self.provider == "zhipuai":
                embeddings = await self._embed_with_zhipuai(texts_to_embed)
            elif self.provider == "huggingface":
                # 实现HuggingFace嵌入
                pass
            elif self.provider == "local":
                embeddings = self._embed_with_local_model(texts_to_embed)
            else:
                raise ValueError(f"不支持的嵌入提供商: {self.provider}")
                
            # 更新缓存
            if self.cache_enabled:
                for text, embedding in zip(texts_to_embed, embeddings):
                    self._cache[text] = embedding
                    
                # 合并缓存命中和新嵌入
                result = []
                embed_index = 0
                
                for hit in cache_hits:
                    if hit is not None:
                        result.append(hit)
                    else:
                        result.append(embeddings[embed_index])
                        embed_index += 1
                        
                embeddings = result
                
            embedding_time = time.time() - start_time
            logger.info(f"嵌入完成: {len(texts)} 个文本, 耗时: {embedding_time:.2f}秒")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"嵌入过程中发生错误: {str(e)}")
            # 返回全零嵌入作为回退
            return [np.zeros(self.dimension) for _ in range(len(texts_to_embed))]
    
    async def embed_query(self, query: str) -> np.ndarray:
        """
        嵌入查询文本
        
        有些模型对查询和文档使用不同的嵌入方式
        
        Args:
            query: 查询文本
            
        Returns:
            查询的向量表示
        """
        return await self.embed_text(query)
    
    async def _embed_with_openai(self, texts: List[str]) -> List[np.ndarray]:
        """使用OpenAI API嵌入文本"""
        if not self.client:
            raise ValueError("OpenAI客户端未初始化")
        
        all_embeddings = []
        # 分批处理以避免API限制
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model_name,
                    input=batch
                )
                
                # 从响应中提取嵌入
                batch_embeddings = [np.array(item.embedding) for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"OpenAI嵌入API错误: {str(e)}")
                # 添加零向量作为回退
                for _ in range(len(batch)):
                    all_embeddings.append(np.zeros(self.dimension))
        
        return all_embeddings
    
    async def _embed_with_zhipuai(self, texts: List[str]) -> List[np.ndarray]:
        """使用智谱AI嵌入服务嵌入文本"""
        if not self.client:
            raise ValueError("智谱AI客户端未初始化")
        
        all_embeddings = []
        # 分批处理以避免API限制
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                # 智谱AI嵌入API调用（注意：智谱API可能是同步的，需要在异步函数中处理）
                import asyncio
                
                # 创建嵌入请求参数
                params = {
                    "model": self.model_name,  # 例如 "embedding-3"
                    "input": batch,
                }
                
                # 如果模型支持自定义维度，添加dimensions参数
                if "embedding-3" in self.model_name:
                    params["dimensions"] = self.dimension
                
                # 使用线程池执行同步API调用
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: self.client.embeddings.create(**params)
                )
                
                # 从响应中提取嵌入
                batch_embeddings = [np.array(item.embedding) for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"智谱AI嵌入API错误: {str(e)}")
                # 添加零向量作为回退
                for _ in range(len(batch)):
                    all_embeddings.append(np.zeros(self.dimension))
        
        return all_embeddings
    
    def _embed_with_local_model(self, texts: List[str]) -> List[np.ndarray]:
        """使用本地模型嵌入文本"""
        if not self.client:
            raise ValueError("本地嵌入模型未初始化")
            
        try:
            # sentence-transformers非异步API，但可以批量处理
            embeddings = self.client.encode(texts)
            return [np.array(embedding) for embedding in embeddings]
        except Exception as e:
            logger.error(f"本地嵌入模型错误: {str(e)}")
            return [np.zeros(self.dimension) for _ in range(len(texts))]

def create_embedding_service(config: Dict[str, Any]) -> EmbeddingService:
    """
    从配置创建嵌入服务
    
    Args:
        config: 嵌入服务配置
        
    Returns:
        配置好的EmbeddingService实例
    """
    return EmbeddingService(config) 