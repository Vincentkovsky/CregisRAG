"""
管理API路由
用于系统管理、监控和控制
"""
import logging
import os
import time
import yaml
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from pydantic import BaseModel, Field

# 导入RAG引擎
from app.core.rag_engine import create_rag_engine

# 导入日志处理器
from app.utils.log_handler import log_handler

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
start_time = time.time()  # 记录启动时间

# 依赖项：获取RAG引擎实例
async def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        logger.info("初始化RAG引擎")
        
        # 初始化必要的服务
        from app.core.embedding import create_embedding_service
        from app.core.generation import create_llm_service
        from app.core.storage.storage_service import create_storage_service
        
        # 创建嵌入服务
        embedding_service = create_embedding_service(rag_config.get("embedding", {}))
        await embedding_service.initialize()
        
        # 创建LLM服务
        llm_service = create_llm_service(rag_config.get("llm", {}))
        await llm_service.initialize()
        
        # 创建存储服务
        storage_service = create_storage_service(rag_config.get("storage", {}))
        await storage_service.initialize()
        
        # 创建RAG引擎并传递所有必要的服务
        rag_engine = create_rag_engine(
            rag_config, 
            llm_service=llm_service,
            embedding_service=embedding_service,
            storage_service=storage_service
        )
        
        await rag_engine.initialize_services()
    return rag_engine

# 模型定义
class SystemStatus(BaseModel):
    """系统状态模型"""
    status: str = Field(..., description="系统状态 (healthy, degraded, maintenance)")
    version: str = Field(..., description="系统版本")
    uptime: float = Field(..., description="运行时间（秒）")
    document_count: int = Field(..., description="知识库中的文档数量")
    vector_count: int = Field(..., description="向量存储中的向量数量")
    resources: Dict[str, Any] = Field(..., description="资源使用情况")

class MaintenanceRequest(BaseModel):
    """维护请求模型"""
    action: str = Field(..., description="维护操作 (reindex, optimize, backup, restore)")
    options: Optional[Dict[str, Any]] = Field(None, description="操作选项")

class ServiceStatus(BaseModel):
    """服务状态模型"""
    name: str = Field(..., description="服务名称")
    status: str = Field(..., description="服务状态 (up, down, degraded)")
    latency: float = Field(..., description="平均延迟（毫秒）")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")

# 系统状态端点
@router.get(
    "/admin/status", 
    response_model=SystemStatus,
    summary="获取系统状态",
    description="获取RAG系统的整体状态和健康信息"
)
async def get_system_status(
    rag_engine = Depends(get_rag_engine)
):
    """获取系统的当前状态"""
    try:
        # 收集各个组件的真实状态
        
        # 计算运行时间
        uptime = time.time() - start_time
        
        # 检查向量存储状态
        vector_store_status = "up"
        document_count = 0
        vector_count = 0
        
        try:
            if rag_engine.vector_store:
                # 获取文档计数
                document_count = await rag_engine.vector_store.get_document_count()
                # 获取向量计数
                vector_count = await rag_engine.vector_store.get_vector_count()
        except Exception as e:
            vector_store_status = "degraded"
            logger.warning(f"获取向量存储状态时出错: {e}")
        
        # 检查LLM服务状态
        llm_status = "up"
        try:
            if rag_engine.llm_service:
                # 可以添加LLM服务的健康检查
                pass
        except Exception as e:
            llm_status = "degraded"
            logger.warning(f"获取LLM服务状态时出错: {e}")
        
        # 检查嵌入服务状态
        embedding_status = "up"
        try:
            if rag_engine.embedding_service:
                # 可以添加嵌入服务的健康检查
                pass
        except Exception as e:
            embedding_status = "degraded"
            logger.warning(f"获取嵌入服务状态时出错: {e}")
        
        # 确定整体系统状态
        overall_status = "healthy"
        if vector_store_status != "up" or llm_status != "up" or embedding_status != "up":
            overall_status = "degraded"
        
        # 获取系统资源使用情况
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        disk = psutil.disk_usage('/')
        disk_usage = disk.percent
        
        # 构建响应
        return SystemStatus(
            status=overall_status,
            version="0.1.0",
            uptime=uptime,
            document_count=document_count,
            vector_count=vector_count,
            resources={
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_usage": disk_usage,
                "embedding_queue": 0,  # 可以从实际队列中获取
                "processing_queue": 0   # 可以从实际队列中获取
            }
        )
    except Exception as e:
        logger.error(f"获取系统状态时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )

# 系统维护端点
@router.post(
    "/admin/maintenance", 
    summary="执行系统维护",
    description="执行系统维护操作，如重新索引、优化或备份"
)
async def perform_maintenance(
    background_tasks: BackgroundTasks,
    request: MaintenanceRequest,
    rag_engine = Depends(get_rag_engine)
):
    """
    执行系统维护操作
    - reindex: 重建向量索引
    - optimize: 优化向量存储
    - backup: 创建系统备份
    - restore: 从备份恢复
    """
    try:
        action = request.action
        options = request.options or {}
        
        # 验证动作
        valid_actions = ["reindex", "optimize", "backup", "restore"]
        if action not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的维护操作。允许的操作: {', '.join(valid_actions)}"
            )
        
        # 获取任务ID
        job_id = f"job-{int(time.time())}"
        
        # 在后台任务中执行维护
        background_tasks.add_task(
            execute_maintenance_task, 
            rag_engine=rag_engine,
            action=action,
            options=options,
            job_id=job_id
        )
        
        return {
            "status": "accepted",
            "message": f"开始执行维护操作: {action}",
            "job_id": job_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行维护操作时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行维护操作失败: {str(e)}"
        )

# 服务健康检查端点
@router.get(
    "/admin/services", 
    response_model=List[ServiceStatus],
    summary="获取服务状态",
    description="获取各个组件和服务的健康状态"
)
async def get_services_status(
    rag_engine = Depends(get_rag_engine)
):
    """获取各个服务的健康状态"""
    try:
        services = []
        
        # 检查向量存储状态
        vector_db_status = "up"
        vector_db_latency = 0
        vector_db_details = {}
        
        try:
            if rag_engine.vector_store:
                # 测量向量存储延迟
                start = time.time()
                await rag_engine.vector_store.get_document_count()
                vector_db_latency = (time.time() - start) * 1000  # 转换为毫秒
                
                # 获取向量存储详情
                vector_db_details = {
                    "provider": rag_engine.vector_store.__class__.__name__,
                    "collections": 1,  # 可以从向量存储中获取实际值
                    "document_count": await rag_engine.vector_store.get_document_count()
                }
        except Exception as e:
            vector_db_status = "down"
            logger.warning(f"检查向量存储状态时出错: {e}")
        
        services.append(ServiceStatus(
            name="vector_db",
            status=vector_db_status,
            latency=vector_db_latency,
            details=vector_db_details
        ))
        
        # 检查LLM服务状态
        llm_status = "up"
        llm_latency = 0
        llm_details = {}
        
        try:
            if rag_engine.llm_service:
                # 测量LLM服务延迟
                # 注意：这里只是简单调用，可能需要更复杂的健康检查
                start = time.time()
                await rag_engine.llm_service.generate(
                    prompt="Hello, this is a test.",
                    system_message="You are a helpful assistant."
                )
                llm_latency = (time.time() - start) * 1000  # 转换为毫秒
                
                # 获取LLM服务详情
                llm_details = {
                    "provider": rag_engine.llm_service.__class__.__name__,
                    "model": rag_engine.llm_service.model_name if hasattr(rag_engine.llm_service, 'model_name') else "unknown"
                }
        except Exception as e:
            llm_status = "down"
            logger.warning(f"检查LLM服务状态时出错: {e}")
        
        services.append(ServiceStatus(
            name="llm_service",
            status=llm_status,
            latency=llm_latency,
            details=llm_details
        ))
        
        # 检查嵌入服务状态
        embedding_status = "up"
        embedding_latency = 0
        embedding_details = {}
        
        try:
            if rag_engine.embedding_service:
                # 测量嵌入服务延迟
                start = time.time()
                await rag_engine.embedding_service.embed_query("This is a test query.")
                embedding_latency = (time.time() - start) * 1000  # 转换为毫秒
                
                # 获取嵌入服务详情
                embedding_details = {
                    "model": rag_engine.embedding_service.model_name if hasattr(rag_engine.embedding_service, 'model_name') else "unknown",
                    "dimension": rag_engine.embedding_service.dimension if hasattr(rag_engine.embedding_service, 'dimension') else 0
                }
        except Exception as e:
            embedding_status = "down"
            logger.warning(f"检查嵌入服务状态时出错: {e}")
        
        services.append(ServiceStatus(
            name="embedding_service",
            status=embedding_status,
            latency=embedding_latency,
            details=embedding_details
        ))
        
        # 检查文档处理服务状态
        doc_processor_status = "up"
        
        try:
            if rag_engine.ingest_service:
                # 可以添加文档处理服务的健康检查
                pass
        except Exception as e:
            doc_processor_status = "down"
            logger.warning(f"检查文档处理服务状态时出错: {e}")
        
        services.append(ServiceStatus(
            name="document_processor",
            status=doc_processor_status,
            latency=0,  # 文档处理通常是异步的，没有直接的延迟测量
            details={
                "queue_size": 0,  # 可以从实际队列中获取
                "processed_last_hour": 0  # 可以从实际统计中获取
            }
        ))
        
        return services
    except Exception as e:
        logger.error(f"获取服务状态时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务状态失败: {str(e)}"
        )

# 清除知识库端点
@router.post(
    "/admin/clear", 
    summary="清除知识库",
    description="清除知识库中的所有文档和向量"
)
async def clear_knowledge_base(
    rag_engine = Depends(get_rag_engine)
):
    """清除知识库中的所有文档和向量"""
    try:
        if not rag_engine.vector_store:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="向量存储不可用"
            )
            
        # 清除向量存储
        await rag_engine.vector_store.clear()
        
        # 清除原始文件
        try:
            raw_dir = Path("data/raw")
            if raw_dir.exists():
                for file in raw_dir.glob("*"):
                    if file.is_file():
                        os.remove(file)
            
            # 清除状态文件
            status_dir = Path("data/status")
            if status_dir.exists():
                for file in status_dir.glob("*"):
                    if file.is_file():
                        os.remove(file)
        except Exception as e:
            logger.warning(f"清除文件时出错: {e}")
            
        return {
            "status": "success",
            "message": "知识库已清除"
        }
    except Exception as e:
        logger.error(f"清除知识库时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清除知识库失败: {str(e)}"
        )

# 获取系统统计信息
@router.get(
    "/admin/statistics", 
    summary="获取系统统计信息",
    description="获取系统使用和性能统计信息"
)
async def get_statistics(
    rag_engine = Depends(get_rag_engine)
):
    """获取系统使用和性能统计信息"""
    try:
        # 收集向量存储统计信息
        vector_stats = {}
        if rag_engine.vector_store:
            try:
                vector_stats = {
                    "document_count": await rag_engine.vector_store.get_document_count(),
                    "vector_count": await rag_engine.vector_store.get_vector_count(),
                    "collection_size": 0  # 可以从向量存储中获取
                }
            except Exception as e:
                logger.error(f"获取向量存储统计信息时出错: {e}")
                
        # 从LogHandler获取查询统计信息
        query_stats = log_handler.get_query_stats()
        
        # 收集文档统计信息
        doc_stats = {
            "total_documents": vector_stats.get("document_count", 0),
            "documents_by_type": {},
            "avg_chunks_per_document": 0
        }
        
        # 收集系统性能统计信息
        perf_stats = {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "avg_response_time": 0
        }
        
        return {
            "vector_store": vector_stats,
            "queries": query_stats,
            "documents": doc_stats,
            "performance": perf_stats,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"获取统计信息时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )

# 新增：获取最近查询历史
@router.get(
    "/admin/recent-queries", 
    summary="获取最近查询历史",
    description="获取系统中最近处理的查询记录"
)
async def get_recent_queries(limit: int = 10):
    """获取最近的查询记录"""
    try:
        # 从LogHandler获取最近查询
        recent_queries = log_handler.get_recent_queries(limit=limit)
        return {
            "queries": recent_queries,
            "count": len(recent_queries)
        }
    except Exception as e:
        logger.error(f"获取最近查询记录时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最近查询记录失败: {str(e)}"
        )

# 新增：获取系统错误日志
@router.get(
    "/admin/error-logs", 
    summary="获取系统错误日志",
    description="获取系统中记录的错误日志"
)
async def get_error_logs(limit: int = 10):
    """获取系统错误日志"""
    try:
        # 从LogHandler获取最近错误
        recent_errors = log_handler.get_recent_errors(limit=limit)
        return {
            "errors": recent_errors,
            "count": len(recent_errors)
        }
    except Exception as e:
        logger.error(f"获取错误日志时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取错误日志失败: {str(e)}"
        )

# 辅助函数：执行维护任务
async def execute_maintenance_task(rag_engine, action: str, options: Dict[str, Any], job_id: str):
    """在后台执行维护任务"""
    logger.info(f"开始执行维护任务: {action}, 任务ID: {job_id}")
    
    try:
        # 创建状态文件
        os.makedirs("data/jobs", exist_ok=True)
        status_file = f"data/jobs/{job_id}.json"
        
        # 更新初始状态
        update_job_status(job_id, "running", 0, None)
        
        if action == "reindex":
            # 重建索引
            if not rag_engine.vector_store:
                raise ValueError("向量存储不可用")
                
            # 获取所有文档
            docs = await rag_engine.vector_store.get_all_documents()
            total_docs = len(docs)
            
            # 清除现有索引
            await rag_engine.vector_store.clear()
            update_job_status(job_id, "running", 30, None)
            
            # 重新索引
            for i, doc in enumerate(docs):
                # 重新嵌入和存储文档
                text = doc.get("text", "")
                metadata = doc.get("metadata", {})
                
                if text:
                    embedding = await rag_engine.embedding_service.embed_text(text)
                    await rag_engine.vector_store.add_vectors([embedding], [text], [metadata])
                
                # 更新进度
                progress = 30 + int(70 * (i + 1) / total_docs)
                update_job_status(job_id, "running", progress, None)
                
        elif action == "optimize":
            # 优化向量存储
            if not rag_engine.vector_store:
                raise ValueError("向量存储不可用")
                
            # 如果向量存储支持优化操作
            if hasattr(rag_engine.vector_store, "optimize") and callable(getattr(rag_engine.vector_store, "optimize")):
                await rag_engine.vector_store.optimize()
                
            update_job_status(job_id, "running", 100, None)
                
        elif action == "backup":
            # 创建备份
            backup_dir = options.get("backup_dir", "data/backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_name = f"backup_{time.strftime('%Y%m%d_%H%M%S')}"
            backup_path = os.path.join(backup_dir, backup_name)
            os.makedirs(backup_path, exist_ok=True)
            
            # 备份原始文件
            update_job_status(job_id, "running", 20, None)
            
            raw_dir = Path("data/raw")
            if raw_dir.exists():
                os.makedirs(os.path.join(backup_path, "raw"), exist_ok=True)
                for file in raw_dir.glob("*"):
                    if file.is_file():
                        import shutil
                        shutil.copy2(file, os.path.join(backup_path, "raw", file.name))
            
            # 备份状态文件
            update_job_status(job_id, "running", 40, None)
            
            status_dir = Path("data/status")
            if status_dir.exists():
                os.makedirs(os.path.join(backup_path, "status"), exist_ok=True)
                for file in status_dir.glob("*"):
                    if file.is_file():
                        import shutil
                        shutil.copy2(file, os.path.join(backup_path, "status", file.name))
            
            # 备份向量存储 (如果支持)
            update_job_status(job_id, "running", 60, None)
            
            if hasattr(rag_engine.vector_store, "backup") and callable(getattr(rag_engine.vector_store, "backup")):
                await rag_engine.vector_store.backup(os.path.join(backup_path, "vectors"))
            
            update_job_status(job_id, "running", 100, None)
            
        elif action == "restore":
            # 从备份恢复
            backup_path = options.get("backup_path")
            if not backup_path or not os.path.exists(backup_path):
                raise ValueError(f"无效的备份路径: {backup_path}")
            
            # 恢复向量存储 (如果支持)
            update_job_status(job_id, "running", 30, None)
            
            if hasattr(rag_engine.vector_store, "restore") and callable(getattr(rag_engine.vector_store, "restore")):
                vector_backup = os.path.join(backup_path, "vectors")
                if os.path.exists(vector_backup):
                    await rag_engine.vector_store.restore(vector_backup)
            
            # 恢复原始文件
            update_job_status(job_id, "running", 60, None)
            
            raw_backup = os.path.join(backup_path, "raw")
            if os.path.exists(raw_backup):
                os.makedirs("data/raw", exist_ok=True)
                for file in os.listdir(raw_backup):
                    import shutil
                    src = os.path.join(raw_backup, file)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join("data/raw", file))
            
            # 恢复状态文件
            update_job_status(job_id, "running", 90, None)
            
            status_backup = os.path.join(backup_path, "status")
            if os.path.exists(status_backup):
                os.makedirs("data/status", exist_ok=True)
                for file in os.listdir(status_backup):
                    import shutil
                    src = os.path.join(status_backup, file)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join("data/status", file))
            
            update_job_status(job_id, "running", 100, None)
            
        # 完成任务
        update_job_status(job_id, "completed", 100, None)
        logger.info(f"维护任务完成: {action}, 任务ID: {job_id}")
        
    except Exception as e:
        logger.error(f"执行维护任务时出错: {action}, 任务ID: {job_id}, 错误: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0, str(e))

# 辅助函数：更新任务状态
def update_job_status(job_id: str, status: str, progress: float, error: Optional[str]):
    """更新任务状态文件"""
    try:
        import json
        
        status_file = f"data/jobs/{job_id}.json"
        status_data = {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "error": error,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"更新任务状态文件时出错: {job_id} - {str(e)}") 