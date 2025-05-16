"""
数据摄取API路由
处理文档上传、处理和向量化
"""
import logging
import os
import time
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from uuid import uuid4
from fastapi.responses import FileResponse

# 导入RAG引擎
from app.core.rag_engine import create_rag_engine

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

# 依赖项：获取RAG引擎实例
async def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        logger.info("初始化RAG引擎")
        rag_engine = create_rag_engine(rag_config)
        await rag_engine.initialize_services()
    return rag_engine

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
    metadata: Optional[str] = Form(None),
    rag_engine = Depends(get_rag_engine)
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
        
        # 使用RAG引擎的摄取服务处理文档
        background_tasks.add_task(
            process_document_with_rag, 
            rag_engine=rag_engine,
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
    request: URLIngestRequest,
    rag_engine = Depends(get_rag_engine)
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
        
        # 使用RAG引擎处理URL
        background_tasks.add_task(
            process_url_with_rag, 
            rag_engine=rag_engine,
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

@router.get(
    "/ingest/status/{document_id}", 
    response_model=IngestStatusResponse,
    summary="获取文档处理状态",
    description="获取特定文档的处理状态"
)
async def get_ingest_status(
    document_id: str,
    rag_engine = Depends(get_rag_engine)
):
    """获取特定文档的处理状态"""
    try:
        # 首先检查状态文件，因为它包含最详细的信息
        status_file = Path(f"data/status/{document_id}.json")
        if status_file.exists():
            import json
            try:
                with open(status_file, "r", encoding='utf-8') as f:
                    status_data = json.load(f)
                    
                return IngestStatusResponse(
                    document_id=document_id,
                    status=status_data.get("status", "processing"),
                    progress=status_data.get("progress", 50.0),
                    error=status_data.get("error"),
                    created_at=status_data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
                )
            except json.JSONDecodeError as e:
                logger.error(f"解析状态文件失败: {e}")
                # 如果状态文件损坏，继续检查其他方法
        
        # 检查向量存储中是否有该文档的向量
        if rag_engine and rag_engine.vector_store:
            doc_exists = await rag_engine.vector_store.document_exists(document_id)
            
            if doc_exists:
                return IngestStatusResponse(
                    document_id=document_id,
                    status="completed",
                    progress=100.0,
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime(f"data/raw/{document_id}.json")))
                )
        
        # 检查原始文件是否存在
        raw_files = list(Path("data/raw").glob(f"{document_id}.*"))
        if raw_files:
            return IngestStatusResponse(
                document_id=document_id,
                status="processing",
                progress=25.0,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getctime(raw_files[0])))
            )
            
        # 文档不存在
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到文档ID: {document_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档状态时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档状态失败: {str(e)}"
        )

@router.get(
    "/ingest/documents", 
    summary="列出所有文档",
    description="获取所有已摄取文档的列表"
)
async def list_documents(
    rag_engine = Depends(get_rag_engine)
):
    """获取所有已摄取文档的列表"""
    try:
        # 在实际应用中，应该从向量存储或数据库中检索文档列表
        # 这里我们将使用RAG引擎的方法
        
        if not rag_engine.vector_store:
            return {"documents": []}
            
        # 获取所有文档的元数据
        documents = await rag_engine.vector_store.get_all_documents_metadata()
        
        # 使用字典来合并源自同一文档的多个块
        doc_groups = {}
        
        for doc in documents:
            # 尝试提取源文档的标识符
            # 首先检查文件路径，它对于同一文档的所有块应该相同
            file_path = doc.get("file_path", "")
            original_id = doc.get("original_document_id", "")
            
            # 如果没有原始文档ID，我们从文档ID中提取
            # 例如，从"doc_1747398373_0"中提取"1747398373"作为分组标识符
            if not original_id and "_" in doc.get("document_id", ""):
                parts = doc.get("document_id", "").split("_")
                if len(parts) >= 3:
                    # 使用中间部分作为原始文档标识符
                    original_id = parts[1]
            
            # 如果我们有文件路径或原始ID，使用它作为分组键
            group_key = file_path or original_id
            
            # 如果没有有效的分组键，使用文件名作为分组键
            if not group_key:
                group_key = doc.get("filename", doc.get("document_id", ""))
            
            # 将文档添加到相应的组
            if group_key not in doc_groups:
                doc_groups[group_key] = {
                    "document_id": original_id or doc.get("document_id", "").split("_")[0] + "_" + original_id if original_id else doc.get("document_id", ""),
                    "name": doc.get("filename", "未知文件"),
                    "upload_date": doc.get("upload_time", ""),
                    "file_size": 0,
                    "status": "completed",
                    "file_type": doc.get("file_type", ""),
                    "chunk_count": 0,
                    "chunks": [],
                    "metadata": {}
                }
            
            # 更新组中的文档信息
            group = doc_groups[group_key]
            
            # 更新文件大小（如果当前块的文件大小更大）
            file_size = 0
            if "file_size" in doc:
                file_size = doc.get("file_size", 0)
            elif file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            
            if file_size > group["file_size"]:
                group["file_size"] = file_size
            
            # 增加块计数
            group["chunk_count"] += 1
            
            # 添加块到块列表
            group["chunks"].append(doc)
            
            # 合并元数据（保留块的信息到metadata.chunks中）
            if "metadata" not in group:
                group["metadata"] = {}
            
            # 复制主要元数据字段（除了块特定的内容）
            for key, value in doc.items():
                if key not in ["chunk_index", "document_id"]:
                    group["metadata"][key] = value
        
        # 获取状态文件信息并更新状态
        for group_key, group in doc_groups.items():
            # 尝试查找关联的状态文件
            orig_doc_id = group["document_id"].split("_")[0] if "_" in group["document_id"] else group["document_id"]
            try:
                status_files = list(Path("data/status").glob(f"{orig_doc_id}*.json"))
                if status_files:
                    import json
                    with open(status_files[0], "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                        group["status"] = status_data.get("status", "completed")
            except Exception as e:
                logger.warning(f"读取状态文件失败: {e}")
        
        # 将合并后的文档转换为列表
        formatted_docs = list(doc_groups.values())
            
        return {"documents": formatted_docs}
        
    except Exception as e:
        logger.error(f"列出文档时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出文档失败: {str(e)}"
        )

@router.delete(
    "/ingest/documents/{document_id}", 
    summary="删除文档",
    description="从知识库中删除特定文档"
)
async def delete_document(
    document_id: str,
    rag_engine = Depends(get_rag_engine)
):
    """从知识库中删除特定文档"""
    try:
        # 在实际应用中，应该使用RAG引擎从向量存储和文件系统中删除文档
        
        if not rag_engine.vector_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"无法访问向量存储"
            )
            
        # 使用RAG引擎删除文档
        result = await rag_engine.delete_document(document_id)
        
        # 删除原始文件
        try:
            raw_files = list(Path("data/raw").glob(f"{document_id}.*"))
            for file in raw_files:
                os.remove(file)
                
            # 删除状态文件
            status_file = Path(f"data/status/{document_id}.json")
            if status_file.exists():
                os.remove(status_file)
        except Exception as e:
            logger.warning(f"删除文件时出错: {e}")
            
        return {
            "status": "success", 
            "message": f"文档 {document_id} 已从知识库中删除",
            "document_id": document_id
        }
        
    except Exception as e:
        logger.error(f"删除文档时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}"
        )

# 辅助函数：使用RAG引擎处理文档
async def process_document_with_rag(rag_engine, document_id: str, file_path: str, metadata: Dict[str, Any]):
    """使用RAG引擎处理文档"""
    
    # 确保状态目录存在
    os.makedirs("data/status", exist_ok=True)
    
    # 创建状态文件
    status_file = f"data/status/{document_id}.json"
    update_status(document_id, "processing", 0, None)
    
    try:
        logger.info(f"开始处理文档: {document_id}")
        
        # 检查rag_engine是否已初始化
        if not rag_engine:
            error_msg = "RAG引擎未初始化"
            logger.error(error_msg)
            update_status(document_id, "failed", 0, error_msg)
            return {"error": error_msg, "document_id": document_id}
            
        # 检查rag_engine.ingest_service是否存在
        if not rag_engine.ingest_service:
            # 尝试重新初始化服务
            logger.warning("文档摄入服务未初始化，尝试初始化...")
            try:
                success = await rag_engine.initialize_services()
                if not success or not rag_engine.ingest_service:
                    error_msg = "无法初始化文档摄入服务"
                    logger.error(error_msg)
                    update_status(document_id, "failed", 0, error_msg)
                    return {"error": error_msg, "document_id": document_id}
            except Exception as init_error:
                error_msg = f"初始化服务失败: {str(init_error)}"
                logger.error(error_msg)
                update_status(document_id, "failed", 0, error_msg)
                return {"error": error_msg, "document_id": document_id}
        
        # 使用RAG引擎的ingest_document方法
        result = await rag_engine.ingest_document(
            file_path=file_path,
            metadata=metadata
        )
        
        # 更新状态
        update_status(document_id, "completed", 100, None)
        
        logger.info(f"文档处理完成: {document_id}")
        return result
        
    except ValueError as ve:
        error_msg = str(ve)
        logger.error(f"处理文档时出错: {document_id} - {error_msg}")
        update_status(document_id, "failed", 0, error_msg)
        
        # 如果是已知的服务未初始化错误，给出更明确的错误信息
        if "未初始化" in error_msg:
            error_msg = f"服务未初始化: {error_msg} - 请确保系统配置正确并重新启动服务"
            
        return {"error": error_msg, "document_id": document_id}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理文档时出错: {document_id} - {error_msg}", exc_info=True)
        update_status(document_id, "failed", 0, error_msg)
        return {"error": error_msg, "document_id": document_id}

# 辅助函数：使用RAG引擎处理URL
async def process_url_with_rag(rag_engine, document_id: str, url: str, metadata: Dict[str, Any]):
    """使用RAG引擎处理URL"""
    
    # 确保状态目录存在
    os.makedirs("data/status", exist_ok=True)
    
    # 创建状态文件
    update_status(document_id, "processing", 0, None)
    
    try:
        logger.info(f"开始处理URL: {url} (ID: {document_id})")
        
        # 检查rag_engine是否已初始化
        if not rag_engine:
            error_msg = "RAG引擎未初始化"
            logger.error(error_msg)
            update_status(document_id, "failed", 0, error_msg)
            return {"error": error_msg, "document_id": document_id}
            
        # 检查rag_engine.ingest_service是否存在
        if not rag_engine.ingest_service:
            # 尝试重新初始化服务
            logger.warning("文档摄入服务未初始化，尝试初始化...")
            try:
                success = await rag_engine.initialize_services()
                if not success or not rag_engine.ingest_service:
                    error_msg = "无法初始化文档摄入服务"
                    logger.error(error_msg)
                    update_status(document_id, "failed", 0, error_msg)
                    return {"error": error_msg, "document_id": document_id}
            except Exception as init_error:
                error_msg = f"初始化服务失败: {str(init_error)}"
                logger.error(error_msg)
                update_status(document_id, "failed", 0, error_msg)
                return {"error": error_msg, "document_id": document_id}
        
        # 导入请求库并抓取页面
        import requests
        from bs4 import BeautifulSoup
        
        # 抓取URL
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # 确保请求成功
        
        # 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取主要文本 (简单版本)
        # 在实际应用中，应该使用更复杂的方法提取有用的内容
        main_text = soup.get_text(separator='\n', strip=True)
        
        # 保存原始HTML
        os.makedirs("data/raw", exist_ok=True)
        with open(f"data/raw/{document_id}.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # 更新状态
        update_status(document_id, "processing", 50, None)
        
        # 使用RAG引擎的ingest_text方法
        result = await rag_engine.ingest_text(
            text=main_text,
            metadata=metadata
        )
        
        # 更新状态
        update_status(document_id, "completed", 100, None)
        
        logger.info(f"URL处理完成: {url} (ID: {document_id})")
        return result
        
    except ValueError as ve:
        error_msg = str(ve)
        logger.error(f"处理URL时出错: {url} (ID: {document_id}) - {error_msg}")
        update_status(document_id, "failed", 0, error_msg)
        
        # 如果是已知的服务未初始化错误，给出更明确的错误信息
        if "未初始化" in error_msg:
            error_msg = f"服务未初始化: {error_msg} - 请确保系统配置正确并重新启动服务"
            
        return {"error": error_msg, "document_id": document_id}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理URL时出错: {url} (ID: {document_id}) - {error_msg}", exc_info=True)
        update_status(document_id, "failed", 0, error_msg)
        return {"error": error_msg, "document_id": document_id}

# 辅助函数：更新状态文件
def update_status(document_id: str, status: str, progress: float, error: Optional[str]):
    """更新文档处理状态"""
    try:
        import json
        
        status_file = f"data/status/{document_id}.json"
        status_data = {
            "document_id": document_id,
            "status": status,
            "progress": progress,
            "error": error,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"更新状态文件时出错: {document_id} - {str(e)}")

# 下载文档
@router.get(
    "/ingest/documents/{document_id}/download", 
    summary="下载文档",
    description="下载原始文档文件"
)
async def download_document(
    document_id: str,
    rag_engine = Depends(get_rag_engine)
):
    """下载原始文档文件"""
    try:
        # 查找原始文件
        raw_dir = "data/raw"
        file_path = None
        
        # 首先，检查文档ID是否是简化格式（如"1747398373"而不是"doc_1747398373_0"）
        # 如果是，我们需要找到对应的实际文档ID
        if not document_id.startswith("doc_"):
            # 获取所有文档元数据
            documents = await rag_engine.vector_store.get_all_documents_metadata()
            
            # 检查是否有任何文档的ID包含这个ID
            matching_docs = []
            for doc in documents:
                if "_" in doc.get("document_id", "") and document_id in doc.get("document_id", ""):
                    matching_docs.append(doc)
            
            if matching_docs:
                # 使用第一个匹配的文档获取文件路径
                first_doc = matching_docs[0]
                file_path = first_doc.get("file_path", "")
                
                # 如果文件路径可用且存在，直接使用它
                if file_path and os.path.exists(file_path):
                    logger.info(f"使用文件路径找到文档: {file_path}")
                else:
                    # 尝试通过匹配文档ID前缀的方式找到文件
                    for file in os.listdir(raw_dir):
                        # 检查文件名是否包含文档ID（处理UUID或数字ID格式）
                        if document_id in file:
                            file_path = os.path.join(raw_dir, file)
                            logger.info(f"通过ID部分匹配找到文档: {file_path}")
                            break
            else:
                # 如果没有找到匹配的文档，尝试直接在文件系统中查找
                for file in os.listdir(raw_dir):
                    if document_id in file:
                        file_path = os.path.join(raw_dir, file)
                        logger.info(f"直接在文件系统中找到文档: {file_path}")
                        break
        else:
            # 如果是完整格式的文档ID，按原始逻辑处理
            # 检查文档是否存在
            doc_exists = await rag_engine.vector_store.document_exists(document_id)
            if not doc_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"文档 {document_id} 不存在"
                )
            
            # 遍历目录查找精确匹配的文件
            for file in os.listdir(raw_dir):
                if file.startswith(document_id):
                    file_path = os.path.join(raw_dir, file)
                    logger.info(f"通过精确ID匹配找到文档: {file_path}")
                    break
        
        # 如果未找到文件，尝试一种备选方案：查找文件元数据中包含的信息
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"未通过常规途径找到文档 {document_id}，尝试元数据检索")
            
            # 查询所有状态文件
            status_files = list(Path("data/status").glob("*.json"))
            for status_file in status_files:
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                        if document_id in status_file.stem or document_id in status_data.get("document_id", ""):
                            # 关联的原始文档ID
                            orig_id = status_file.stem
                            # 查找相关文件
                            for file in os.listdir(raw_dir):
                                if file.startswith(orig_id):
                                    file_path = os.path.join(raw_dir, file)
                                    logger.info(f"通过状态文件找到文档: {file_path}")
                                    break
                            if file_path:
                                break
                except Exception as e:
                    logger.warning(f"读取状态文件失败: {e}")
        
        # 最后检查是否找到了文件
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"原始文档文件未找到"
            )
        
        # 确定文件类型和名称
        filename = os.path.basename(file_path)
        file_extension = os.path.splitext(filename)[1]
        
        # 设置响应头，使用文件原始类型
        media_type = "application/octet-stream"
        if file_extension == ".pdf":
            media_type = "application/pdf"
        elif file_extension == ".txt":
            media_type = "text/plain"
        elif file_extension == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_extension == ".html":
            media_type = "text/html"
        
        return FileResponse(
            path=file_path,
            filename=f"document-{document_id}{file_extension}",
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文档时出错: {document_id} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文档失败: {str(e)}"
        ) 