"""
CregisRAG API 主入口文件
"""
import yaml
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
import asyncio
import time
from typing import Dict, Any, List, Optional
import re
import json
import mimetypes
from fastapi import File, UploadFile, HTTPException, Form, Body, Query, BackgroundTasks, Depends, Response
from pydantic import BaseModel, Field
import aiofiles
from fastapi.exceptions import RequestValidationError

# 导入日志处理工具
from app.utils.log_handler import record_error

# 模型定义
class QueryRequest(BaseModel):
    query: str
    filter: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    processing_time: float

# 导入环境变量加载工具
from app.utils.env_loader import load_api_keys, process_config, load_env_variables

# 导入核心服务
from app.core.embedding import create_embedding_service
from app.core.generation import create_llm_service
from app.core.storage.storage_service import create_storage_service
from app.core.rag_engine import RAGEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量中的API密钥
api_keys = load_api_keys()
if api_keys:
    logger.info(f"已加载 {len(api_keys)} 个API密钥")
else:
    logger.warning("未加载任何API密钥，请确保.env文件配置正确")

# 加载配置
async def load_config():
    """异步加载配置文件"""
    config_path = Path("config.yml")
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
        # 处理配置中的环境变量引用
        return process_config(config)

# 同步方式加载配置，用于应用启动前
def load_config_sync():
    config_path = Path("config.yml")
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
        # 处理配置中的环境变量引用
        return process_config(config)

config = load_config_sync()

# 加载环境变量
load_env_variables()

# 创建 FastAPI 应用
app = FastAPI(
    title=config["frontend"]["title"],
    description=config["frontend"]["description"],
    version="0.1.0",
)

# 配置跨域资源共享
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["app"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
rag_engine = None

# 创建启动日志文件
startup_log_handler = logging.FileHandler("logs/startup.log", mode="w")
startup_logger = logging.getLogger("startup")
startup_logger.setLevel(logging.INFO)
startup_logger.addHandler(startup_log_handler)
startup_logger.propagate = False

# 全局异常处理
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # 记录错误详情
    error_message = str(exc)
    endpoint = request.url.path
    method = request.method
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    # 使用LogHandler记录错误
    record_error(
        error_type="unhandled_exception",
        message=error_message,
        component=f"{method}_{endpoint}",
        details={
            "path": str(request.url),
            "method": method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params)
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "内部服务器错误"},
    )

# 添加请求验证错误处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_message = str(exc)
    endpoint = request.url.path
    method = request.method
    logger.error(f"请求验证错误: {error_message}")
    
    # 使用LogHandler记录错误
    record_error(
        error_type="request_validation_error",
        message=error_message,
        component=f"{method}_{endpoint}",
        details={
            "path": str(request.url),
            "method": method,
            "errors": exc.errors()
        }
    )
    
    # 返回标准422错误响应
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

# 根路径端点
@app.get("/", response_class=HTMLResponse)
async def root():
    """
    应用根路径，返回简单的HTML页面
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CregisRAG - 智能检索增强生成系统</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #333;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            h2 {
                color: #444;
                margin-top: 30px;
            }
            code {
                background-color: #f4f4f4;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: monospace;
            }
            .endpoint {
                background-color: #f9f9f9;
                border-left: 4px solid #ddd;
                padding: 10px 15px;
                margin: 10px 0;
            }
            .method {
                font-weight: bold;
                color: #0366d6;
            }
        </style>
    </head>
    <body>
        <h1>CregisRAG - 智能检索增强生成系统</h1>
        <p>欢迎使用CregisRAG，这是一个强大的检索增强生成（RAG）系统，可以帮助你基于自己的知识库构建智能问答应用。</p>
        
        <h2>API文档</h2>
        <p>完整的API文档可以在 <a href="/docs">/docs</a> 或 <a href="/redoc">/redoc</a> 访问。</p>
        
        <h2>主要功能</h2>
        <ul>
            <li>文档上传和知识库构建</li>
            <li>智能查询和回答生成</li>
            <li>基于上下文的精确回答</li>
            <li>完整的源文档引用</li>
            <li>系统状态监控和管理</li>
        </ul>
        
        <h2>主要API端点</h2>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/ingest/upload</code> - 上传文档文件
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/ingest/url</code> - 从URL导入内容
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/query</code> - 查询知识库
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/ingest/documents</code> - 获取所有文档
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/admin/status</code> - 获取系统状态
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/health</code> - 健康检查
        </div>
    </body>
    </html>
    """
    return html_content

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "健康", "version": "0.1.0"}

# 导入和包含API路由
from app.api.routes import query, ingest, admin

# 注册路由
app.include_router(query.router, prefix="/api", tags=["查询"])
app.include_router(ingest.router, prefix="/api", tags=["数据摄取"])
app.include_router(admin.router, prefix="/api", tags=["管理"])

# 挂载静态文件
static_dir = Path("frontend/build")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    await on_startup()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API服务正在关闭...")
    # 在这里可以添加关闭时需要执行的代码，例如：
    # - 关闭数据库连接
    # - 保存缓存 

async def init_document_ingestion():
    """初始化文档摄取服务"""
    global rag_engine
    
    try:
        startup_logger.info("初始化文档摄取服务...")
        # 确保数据目录存在
        os.makedirs("data/documents", exist_ok=True)
        os.makedirs("data/processed", exist_ok=True)
        
        # 已经在RAG引擎创建时初始化了摄取服务
        if rag_engine:
            startup_logger.info("文档摄取服务初始化成功")
            return True
        else:
            startup_logger.error("文档摄取服务初始化失败：RAG引擎未初始化")
            return False
    except Exception as e:
        startup_logger.error(f"初始化文档摄取服务时出错: {str(e)}")
        return False

async def on_startup():
    """应用启动时初始化服务"""
    global rag_engine, config

    startup_logger.info("正在启动CregisRAG服务...")
    startup_time = time.time()

    try:
        # 加载配置
        config_path = os.environ.get("CONFIG_PATH", "config.yml")
        config = await load_config()
        startup_logger.info(f"已加载配置: {config_path}")

        # 初始化服务
        startup_logger.info("初始化嵌入服务...")
        embedding_service = create_embedding_service(config.get("embedding", {}))
        if not await embedding_service.initialize():
            startup_logger.error("嵌入服务初始化失败")
            return False

        startup_logger.info("初始化LLM服务...")
        llm_service = create_llm_service(config.get("llm", {}))
        if not await llm_service.initialize():
            startup_logger.error("LLM服务初始化失败")
            return False

        startup_logger.info("初始化存储服务...")
        storage_service = create_storage_service(config.get("storage", {}))
        if not await storage_service.initialize():
            startup_logger.error("存储服务初始化失败")
            return False

        # 创建RAG引擎
        startup_logger.info("初始化RAG引擎...")
        rag_engine = RAGEngine(
            config=config,
            llm_service=llm_service,
            embedding_service=embedding_service,
            storage_service=storage_service
        )

        # 初始化文档摄取服务
        if not await init_document_ingestion():
            startup_logger.error("文档摄取服务初始化失败")
            return False

        startup_logger.info(f"CregisRAG服务启动完成! 耗时: {time.time() - startup_time:.2f}秒")
        return True

    except Exception as e:
        startup_logger.error(f"服务启动失败: {str(e)}")
        return False

@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    if rag_engine is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "message": "服务尚未完全初始化"}
        )
    return {"status": "ok", "message": "服务运行正常"}

@app.post("/api/query")
async def query(request: QueryRequest):
    """处理RAG查询"""
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG引擎尚未初始化")

    try:
        # 调用RAG引擎处理查询
        result = await rag_engine.process_query(request.query, filter_metadata=request.filter)
        return result
    except Exception as e:
        logging.error(f"处理查询时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")

@app.post("/api/test_llm")
async def test_llm():
    """测试LLM服务"""
    try:
        # 获取rag_engine实例
        if not rag_engine or not rag_engine.llm_service:
            return {"status": "error", "message": "LLM服务未初始化"}
            
        # 发送简单的测试查询
        response = await rag_engine.llm_service.generate(
            prompt="这是一个简单的测试，请回复'测试成功'",
            system_message="你是一个测试系统，请直接回复用户的请求"
        )
        
        return {
            "status": "success",
            "message": "LLM服务工作正常",
            "llm_response": response
        }
    except Exception as e:
        logger.error(f"LLM测试失败: {str(e)}")
        return {
            "status": "error", 
            "message": f"LLM测试失败: {str(e)}"
        }

@app.get("/api/ingest/documents")
async def list_documents():
    """获取所有已摄取的文档列表"""
    try:
        # 获取rag_engine实例
        if not rag_engine or not rag_engine.storage_service:
            return {"documents": []}
            
        # 获取所有文档元数据
        try:
            if rag_engine.vector_store:
                documents_metadata = await rag_engine.vector_store.get_all_documents_metadata()
                
                # 使用字典来合并源自同一文档的多个块
                doc_groups = {}
                
                for doc in documents_metadata:
                    # 尝试提取源文档的标识符
                    document_id = doc.get("document_id", "")
                    filename = doc.get("filename", doc.get("file_name", "未知文件"))
                    
                    # 使用document_id作为分组键
                    group_key = document_id or filename
                    
                    if group_key not in doc_groups:
                        doc_groups[group_key] = {
                            "document_id": document_id,
                            "name": filename,
                            "upload_date": doc.get("upload_time", ""),
                            "file_type": doc.get("file_type", doc.get("mime_type", "").split("/")[-1]),
                            "chunk_count": 0,
                            "metadata": {}
                        }
                    
                    # 更新组中的文档信息
                    group = doc_groups[group_key]
                    group["chunk_count"] += 1
                    
                    # 合并元数据
                    for key, value in doc.items():
                        if key not in ["chunk_index", "document_id", "preview"]:
                            group["metadata"][key] = value
                
                # 将合并后的文档转换为列表
                formatted_docs = list(doc_groups.values())
                
                return {"documents": formatted_docs}
            else:
                return {"documents": []}
        except Exception as e:
            logger.error(f"获取文档元数据失败: {str(e)}")
            return {"documents": [], "error": str(e)}
    except Exception as e:
        logger.error(f"列出文档时出错: {str(e)}")
        return {"documents": [], "error": str(e)} 