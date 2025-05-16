"""
数据摄取API路由
处理文档上传、处理和向量化
"""
import logging
import os
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from uuid import uuid4

# 使用 APIRouter 而不是直接在 FastAPI 应用上定义路由
router = APIRouter()

# 配置日志
logger = logging.getLogger(__name__)

# 模型定义
class IngestResponse(BaseModel):
    """摄取响应模型"""
    document_id: str = Field(..., description="处理的文档ID")
    filename: str = Field(..., description="原始文件名")
    num_chunks: int = Field(..., description="文档被分成的块数")
    status: str = Field(..., description="处理状态")
    processing_time: float = Field(..., description="处理时间（秒）")
    metadata: Optional[Dict[str, Any]] = Field(None, description="文档元数据")

class IngestStatusResponse(BaseModel):
    """摄取状态响应模型"""
    document_id: str = Field(..., description="文档ID")
    status: str = Field(..., description="处理状态 (pending, processing, completed, failed)")
    progress: float = Field(..., description="处理进度 (0-100%)")
    error: Optional[str] = Field(None, description="如果失败，错误消息")
    created_at: str = Field(..., description="创建时间")

class URLIngestRequest(BaseModel):
    """URL摄取请求模型"""
    url: str = Field(..., description="要摄取的网页URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="可选的文档元数据")

# 文件上传端点
@router.post(
    "/ingest/upload", 
    response_model=IngestResponse, 
    summary="上传并摄取文档",
    description="上传文档文件，处理并将其添加到知识库中"
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None)
):
    """
    上传文档文件（PDF、TXT、DOCX等），处理并将其添加到知识库中
    - 解析文档
    - 分块文本
    - 向量化文本块
    - 存储向量及元数据
    """
    start_time = time.time()
    document_id = str(uuid4())
    
    try:
        # 获取文件名和扩展名
        filename = file.filename
        file_extension = os.path.splitext(filename)[1].lower()
        
        # 检查文件类型
        allowed_extensions = [".pdf", ".txt", ".docx", ".md", ".html"]
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"不支持的文件类型。允许的类型: {', '.join(allowed_extensions)}"
            )
        
        # 读取元数据（如果有）
        doc_metadata = {}
        if metadata:
            import json
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"无法解析元数据JSON: {metadata}")
        
        # 添加基本元数据
        doc_metadata.update({
            "filename": filename,
            "document_id": document_id,
            "file_type": file_extension[1:],  # 移除开头的点
            "upload_time": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 保存上传的文件
        os.makedirs("data/raw", exist_ok=True)
        file_path = f"data/raw/{document_id}{file_extension}"
        
        # 读取文件内容并保存
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 在后台任务中处理文档（异步）
        # 在实际应用中，这里应该调用文档处理、分块和向量化逻辑
        background_tasks.add_task(
            process_document, 
            document_id=document_id,
            file_path=file_path,
            metadata=doc_metadata
        )
        
        # 计算处理时间并返回响应
        processing_time = time.time() - start_time
        
        return IngestResponse(
            document_id=document_id,
            filename=filename,
            num_chunks=0,  # 实际值将在后台任务完成后更新
            status="pending",
            processing_time=processing_time,
            metadata=doc_metadata
        )
        
    except Exception as e:
        logger.error(f"文档摄取过程中出错: {e}", exc_info=True)
        # 清理任何临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理文档失败: {str(e)}"
        )

# 从URL摄取内容
@router.post(
    "/ingest/url", 
    response_model=IngestResponse, 
    summary="从URL摄取内容",
    description="从指定URL抓取内容，处理并将其添加到知识库中"
)
async def ingest_from_url(
    background_tasks: BackgroundTasks,
    request: URLIngestRequest
):
    """
    从URL摄取内容，处理并添加到知识库中
    - 抓取URL内容
    - 解析HTML
    - 提取主要文本内容
    - 分块文本
    - 向量化文本块
    - 存储向量及元数据
    """
    start_time = time.time()
    document_id = str(uuid4())
    
    try:
        url = request.url
        
        # 检查URL格式
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的URL格式。URL必须以http://或https://开头。"
            )
        
        # 准备元数据
        metadata = request.metadata or {}
        metadata.update({
            "source_url": url,
            "document_id": document_id,
            "file_type": "html",
            "upload_time": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 在后台任务中处理URL（异步）
        # 在实际应用中，这里应该调用URL抓取、HTML解析、分块和向量化逻辑
        background_tasks.add_task(
            process_url, 
            document_id=document_id,
            url=url,
            metadata=metadata
        )
        
        # 计算处理时间并返回响应
        processing_time = time.time() - start_time
        
        return IngestResponse(
            document_id=document_id,
            filename=url,  # 使用URL作为"文件名"
            num_chunks=0,  # 实际值将在后台任务完成后更新
            status="pending",
            processing_time=processing_time,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"URL摄取过程中出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理URL失败: {str(e)}"
        )

# 获取摄取状态
@router.get(
    "/ingest/status/{document_id}", 
    response_model=IngestStatusResponse,
    summary="获取文档处理状态",
    description="获取特定文档的处理状态"
)
async def get_ingest_status(document_id: str):
    """获取文档处理的当前状态"""
    try:
        # 在实际应用中，应该从数据库或缓存中获取状态
        # 这里使用示例数据
        return IngestStatusResponse(
            document_id=document_id,
            status="processing",
            progress=65.0,
            error=None,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        logger.error(f"获取摄取状态时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )

# 列出已摄取的文档
@router.get(
    "/ingest/documents", 
    summary="列出所有文档",
    description="获取所有已摄取文档的列表"
)
async def list_documents():
    """获取所有已摄取文档的列表"""
    try:
        # 在实际应用中，应该从数据库中获取文档列表
        # 这里使用示例数据
        return {
            "documents": [
                {
                    "document_id": "doc123",
                    "filename": "示例文档.pdf",
                    "status": "completed",
                    "num_chunks": 15,
                    "upload_time": "2024-06-15 10:30:45",
                    "file_type": "pdf",
                    "metadata": {"source_type": "pdf", "page_count": 5}
                },
                {
                    "document_id": "doc456",
                    "filename": "示例文档2.txt",
                    "status": "completed",
                    "num_chunks": 8,
                    "upload_time": "2024-06-14 15:20:10",
                    "file_type": "txt",
                    "metadata": {"source_type": "text"}
                }
            ],
            "total": 2
        }
    except Exception as e:
        logger.error(f"列出文档时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}"
        )

# 删除文档
@router.delete(
    "/ingest/documents/{document_id}", 
    summary="删除文档",
    description="从知识库中删除特定文档"
)
async def delete_document(document_id: str):
    """从知识库中删除文档及其所有块"""
    try:
        # 在实际应用中，应该:
        # 1. 从向量存储中删除相关向量
        # 2. 从文件存储中删除原始文件
        # 3. 从数据库中删除元数据记录
        
        # 返回成功消息
        return {"status": "success", "message": f"文档 {document_id} 已成功删除"}
    except Exception as e:
        logger.error(f"删除文档时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}"
        )

# ---- 辅助函数 ----

def process_document(document_id: str, file_path: str, metadata: Dict[str, Any]):
    """
    后台任务：处理文档文件
    这个函数会在后台执行，不阻塞API响应
    """
    try:
        logger.info(f"开始处理文档: {document_id}, 文件路径: {file_path}")
        
        # TODO: 实现实际的文档处理逻辑
        # 1. 根据文件类型解析文档
        # 2. 清洗和分块文本
        # 3. 向量化文本块
        # 4. 存储向量和元数据
        # 5. 更新处理状态
        
        # 模拟处理延迟
        time.sleep(2)
        
        logger.info(f"文档处理完成: {document_id}")
    except Exception as e:
        logger.error(f"处理文档 {document_id} 时出错: {e}", exc_info=True)
        # 更新文档状态为失败
        # 在实际应用中，应该更新数据库中的状态记录

def process_url(document_id: str, url: str, metadata: Dict[str, Any]):
    """
    后台任务：处理URL内容
    这个函数会在后台执行，不阻塞API响应
    """
    try:
        logger.info(f"开始处理URL: {url}, 文档ID: {document_id}")
        
        # TODO: 实现实际的URL处理逻辑
        # 1. 抓取URL内容
        # 2. 解析HTML
        # 3. 提取主要文本内容
        # 4. 清洗和分块文本
        # 5. 向量化文本块
        # 6. 存储向量和元数据
        # 7. 更新处理状态
        
        # 模拟处理延迟
        time.sleep(2)
        
        logger.info(f"URL处理完成: {document_id}")
    except Exception as e:
        logger.error(f"处理URL {url} (文档ID: {document_id}) 时出错: {e}", exc_info=True)
        # 更新文档状态为失败
        # 在实际应用中，应该更新数据库中的状态记录 