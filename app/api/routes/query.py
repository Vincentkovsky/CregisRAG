"""
查询API路由
处理用户查询，检索相关上下文，并生成回答
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import time
import yaml
from pathlib import Path

# 导入RAG引擎
from app.core.rag_engine import create_rag_engine

# 导入日志处理工具
from app.utils.log_handler import record_query, record_error

# 使用 APIRouter 而不是直接在 FastAPI 应用上定义路由
router = APIRouter()

# 配置日志
logger = logging.getLogger(__name__)

# 加载配置
def load_config():
    config_path = Path("config.yml")
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

# 初始化RAG引擎
rag_config = load_config()
rag_engine = None

# 请求模型
class QueryRequest(BaseModel):
    query: str = Field(..., description="用户问题", min_length=1)
    top_k: Optional[int] = Field(5, description="要检索的上下文数量")
    filter: Optional[Dict[str, Any]] = Field(None, description="可选的元数据过滤器")
    user_id: Optional[str] = Field(None, description="用户ID，用于个性化和跟踪")

# 回答源模型
class Source(BaseModel):
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    text: str = Field(..., description="相关文本片段")
    score: float = Field(..., description="相关性分数")
    metadata: Optional[Dict[str, Any]] = Field({}, description="文档元数据")

# 响应模型
class QueryResponse(BaseModel):
    query: str = Field(..., description="原始查询")
    answer: str = Field(..., description="生成的回答")
    sources: List[Source] = Field(..., description="用于生成回答的源")
    processing_time: float = Field(..., description="处理时间（秒）")

# 依赖项：获取RAG引擎实例
async def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        logger.info("初始化RAG引擎")
        rag_engine = create_rag_engine(rag_config)
        await rag_engine.initialize_services()
    return rag_engine

# 查询端点
@router.post("/query", response_model=QueryResponse, summary="查询知识库")
async def query_knowledge_base(
    request: QueryRequest, 
    rag_engine = Depends(get_rag_engine)
):
    """
    根据用户查询，从知识库中检索相关信息并生成回答
    """
    start_time = time.time()
    
    try:
        logger.info(f"接收到查询: {request.query}")
        
        # 使用RAG引擎处理查询
        rag_response = await rag_engine.process_query(
            query=request.query,
            top_k=request.top_k,
            filter_metadata=request.filter,
            conversation_id=request.user_id
        )
        
        # 处理响应
        answer = rag_response.get("answer", "")
        sources = [
            Source(
                document_id=src.get("document_id", ""),
                document_name=src.get("document_name", "未知文档"),
                text=src.get("text", ""),
                score=src.get("score", 0.0),
                metadata=src.get("metadata", {})
            )
            for src in rag_response.get("sources", [])
        ]
        
        processing_time = time.time() - start_time
        
        # 转换为原生字典以便于记录
        source_dicts = [
            {
                "document_id": src.document_id,
                "document_name": src.document_name,
                "text": src.text,
                "score": src.score,
                "metadata": src.metadata
            }
            for src in sources
        ]
        
        # 记录查询
        record_query(
            query=request.query,
            answer=answer,
            sources=source_dicts,
            processing_time=processing_time,
            token_usage=rag_response.get("token_usage", {})
        )
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            processing_time=processing_time
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"处理查询时出错: {e}", exc_info=True)
        
        # 记录错误
        record_error(
            error_type="query_processing_error",
            message=str(e),
            component="query_api",
            details={
                "query": request.query,
                "processing_time": processing_time,
                "user_id": request.user_id,
                "filter": request.filter
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理查询失败: {str(e)}"
        )

# 实时查询端点（流式响应）
@router.post("/query/stream", summary="流式查询知识库")
async def stream_query(request: QueryRequest):
    """
    查询知识库并以流式方式返回结果
    
    此端点实现了SSE (Server-Sent Events)，允许渐进式接收LLM生成的回答
    前端可以实时显示回答，而不必等待整个回答生成完成
    """
    # 在此实现流式响应
    # FastAPI支持StreamingResponse，可用于实现SSE
    
    # 示例代码（需要实际实现）:
    # async def event_generator():
    #     # 1. 向量化查询
    #     # 2. 检索相关文档
    #     # 3. 构建提示
    #     # 4. 流式调用LLM API
    #     # 5. 逐步yield结果
    #     return stream
    # return StreamingResponse(event_generator(), media_type="text/event-stream")
    
    # 当前返回未实现的提示
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="流式响应功能尚未实现"
    )

# 相似问题建议端点
@router.post("/query/suggest", summary="获取相似问题建议")
async def suggest_questions(
    query: str,
    rag_engine = Depends(get_rag_engine)
):
    """
    根据用户输入的问题，提供相似问题的建议
    
    当用户开始输入查询时，此端点可用于提供自动补全和建议
    """
    # 尝试使用向量存储来查找相似问题
    try:
        # 向量化查询
        query_vector = await rag_engine.embedding_service.embed_query(query)
        
        # 在向量存储中查找相似问题
        # 假设我们有一个专门存放历史问题的集合
        similar_questions = await rag_engine.vector_store.similarity_search(
            query_vector, 
            top_k=3,
            collection_name="questions"  # 可选参数，如果向量存储支持多个集合
        )
        
        suggestions = [q.get("text", "") for q in similar_questions]
        
        # 如果没有足够的相似问题，生成一些基于模板的建议
        if len(suggestions) < 3:
            default_suggestions = [
                f"{query} 的最佳实践是什么？",
                f"如何优化 {query} 的性能？",
                f"{query} 的常见问题有哪些？"
            ]
            suggestions.extend(default_suggestions[:3 - len(suggestions)])
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.warning(f"获取问题建议时出错: {e}")
        # 出错时返回默认建议
        suggestions = [
            f"{query} 的最佳实践是什么？",
            f"如何优化 {query} 的性能？",
            f"{query} 的常见问题有哪些？"
        ]
        return {"suggestions": suggestions} 