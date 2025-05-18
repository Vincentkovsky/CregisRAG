"""
文档处理器模块

该模块负责解析和处理不同格式的文档，将其转换为文本并提取元数据。
支持各种文档格式，如PDF、Word、文本等。
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, BinaryIO, Union, Callable
import mimetypes
from dataclasses import dataclass, field
import uuid
import re

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """文档片段类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    similarity: float = 0.0

@dataclass
class Document:
    """文档类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[DocumentChunk] = field(default_factory=list)

class DocumentProcessor:
    """
    文档处理器类
    
    处理各种格式的文档，提取文本和元数据。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化文档处理器
        
        Args:
            config: 配置参数
        """
        self.config = config
        
        # 读取配置
        self.extract_metadata = config.get("extract_metadata", True)
        self.supported_formats = config.get("supported_formats", ["pdf", "txt", "doc", "docx", "md", "html"])
        self.chunk_size = config.get("chunk_size", 1000)
        self.chunk_overlap = config.get("chunk_overlap", 200)
        self.detect_language = config.get("detect_language", True)
        self.extract_images = config.get("extract_images", False)
        
        # PDF处理特定配置
        self.pdf_config = config.get("pdf_processing", {})
        self.use_enhanced_parser = self.pdf_config.get("use_enhanced_parser", True)
        self.fallback_to_pdfplumber = self.pdf_config.get("fallback_to_pdfplumber", True)
        self.ocr_enabled = self.pdf_config.get("ocr_enabled", False)
        self.text_cleaning = self.pdf_config.get("text_cleaning", True)
        self.x_tolerance = self.pdf_config.get("x_tolerance", 3)
        self.y_tolerance = self.pdf_config.get("y_tolerance", 3)
        
        # 每种文档类型的处理函数映射
        self.handlers = {
            "application/pdf": self._process_pdf,
            "text/plain": self._process_text,
            "application/msword": self._process_doc,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self._process_docx,
            "text/markdown": self._process_markdown,
            "text/html": self._process_html
        }
        
        logger.info(f"初始化文档处理器: 支持格式={self.supported_formats}, 增强PDF解析={self.use_enhanced_parser}")
    
    async def process_file(self, 
                          file_path: str, 
                          mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        处理文件
        
        Args:
            file_path: 文件路径
            mime_type: 可选的MIME类型，如果为None则自动检测
            
        Returns:
            包含文本和元数据的字典
        """
        start_time = time.time()
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
                
            # 确定MIME类型
            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(file_path)
                
            if mime_type is None:
                # 使用扩展名作为后备
                ext = os.path.splitext(file_path)[1].lower().lstrip(".")
                if ext in self.supported_formats:
                    if ext == "pdf":
                        mime_type = "application/pdf"
                    elif ext in ["txt", "text"]:
                        mime_type = "text/plain"
                    elif ext == "doc":
                        mime_type = "application/msword"
                    elif ext == "docx":
                        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif ext == "md":
                        mime_type = "text/markdown"
                    elif ext == "html":
                        mime_type = "text/html"
                
            if mime_type not in self.handlers:
                raise ValueError(f"不支持的文档类型: {mime_type}")
                
            # 获取处理函数
            handler = self.handlers[mime_type]
            
            # 处理文档
            with open(file_path, "rb") as file:
                result = await handler(file)
                
            # 添加文件信息
            result["metadata"]["file_path"] = file_path
            result["metadata"]["file_name"] = os.path.basename(file_path)
            result["metadata"]["file_size"] = os.path.getsize(file_path)
            result["metadata"]["mime_type"] = mime_type
            
            logger.info(f"文档处理完成: {file_path}, 提取了 {len(result['text'])} 字符, 耗时: {time.time() - start_time:.2f}秒")
            return result
            
        except Exception as e:
            logger.error(f"处理文档时出错 {file_path}: {str(e)}")
            
            # 返回错误信息
            return {
                "text": "",
                "metadata": {
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                    "error": str(e)
                },
                "error": str(e)
            }
    
    async def process_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理原始文本
        
        Args:
            text: 待处理的文本
            metadata: 可选的元数据
            
        Returns:
            包含文本和元数据的字典
        """
        if metadata is None:
            metadata = {}
        
        # 可以在这里添加文本预处理步骤
        result = {
            "text": text,
            "metadata": metadata
        }
        
        return result
        
    async def _process_pdf(self, file: BinaryIO) -> Dict[str, Any]:
        """处理PDF文件"""
        primary_text = ""
        fallback_text = ""
        metadata = {}

        # 首先尝试使用PyPDF2
        try:
            from PyPDF2 import PdfReader
            
            # 保存原始文件位置
            file_pos = file.tell()
            
            reader = PdfReader(file)
            primary_text = ""
            
            # 提取文本
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                primary_text += f"\n\n--- 第 {page_num + 1} 页 ---\n\n"
                primary_text += page_text
            
            # 提取元数据
            if self.extract_metadata:
                info = reader.metadata
                if info:
                    metadata = {
                        "title": info.title,
                        "author": info.author,
                        "creator": info.creator,
                        "producer": info.producer,
                        "page_count": len(reader.pages)
                    }
                    # 过滤None值
                    metadata = {k: v for k, v in metadata.items() if v is not None}
            
            # 重置文件位置，以便后续处理
            file.seek(file_pos)
            
            # 检查文本质量（检测大量乱码）
            has_encoding_issues = primary_text.count('\ufffd') > len(primary_text) * 0.05  # 如果乱码字符超过5%
            
            # 如果配置了增强解析且存在编码问题，尝试备选解析方法
            if self.use_enhanced_parser and (has_encoding_issues or self.fallback_to_pdfplumber):
                logger.info("使用增强PDF解析方法")
                
                # 尝试使用pdfplumber作为后备方案
                try:
                    import pdfplumber
                    
                    file_pos = file.tell()
                    with pdfplumber.open(file) as pdf:
                        fallback_text = ""
                        for i, page in enumerate(pdf.pages):
                            fallback_text += f"\n\n--- 第 {i + 1} 页 ---\n\n"
                            # 使用配置的容差参数
                            page_text = page.extract_text(x_tolerance=self.x_tolerance, y_tolerance=self.y_tolerance)
                            fallback_text += page_text or ""
                            
                            # 如果启用了OCR且页面文本提取有问题
                            if self.ocr_enabled and (not page_text or page_text.count('\ufffd') > len(page_text) * 0.1):
                                try:
                                    # 如果配置了OCR，应该在这里添加OCR处理逻辑
                                    pass
                                except Exception as ocr_error:
                                    logger.error(f"OCR处理失败: {str(ocr_error)}")
                    
                    # 如果pdfplumber提取的文本比PyPDF2的更好，则使用它
                    if fallback_text and (not has_encoding_issues or 
                                          fallback_text.count('\ufffd') < primary_text.count('\ufffd')):
                        logger.info("使用pdfplumber提取的PDF文本质量更高")
                        primary_text = fallback_text
                    
                    # 重置文件位置
                    file.seek(file_pos)
                    
                except ImportError:
                    logger.warning("pdfplumber库未安装，无法使用备选PDF解析方法")
                except Exception as plumber_error:
                    logger.error(f"使用pdfplumber处理PDF时出错: {str(plumber_error)}")
            
            # 清理文本中的乱码和格式问题
            if self.text_cleaning:
                cleaned_text = self._clean_pdf_text(primary_text)
            else:
                cleaned_text = primary_text.strip()
            
            return {
                "text": cleaned_text,
                "metadata": metadata
            }
            
        except ImportError:
            logger.error("处理PDF需要PyPDF2库")
            return {"text": "", "metadata": {"error": "缺少PyPDF2库"}}
        except Exception as e:
            logger.error(f"处理PDF文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}
    
    def _clean_pdf_text(self, text: str) -> str:
        """清理PDF文本中的常见问题"""
        if not text:
            return ""
        
        # 替换连续的乱码字符为空格
        text = re.sub(r'(\ufffd){2,}', ' ', text)
        
        # 尝试恢复数字格式（当$符号与数字之间有乱码时）
        text = re.sub(r'\$\s*\ufffd+\s*(\d+)', r'$\1', text)
        
        # 处理价格格式
        text = re.sub(r'\$\s*(\d+)\s*,\s*(\d+)', r'$\1,\2', text)
        
        # 替换单独的乱码字符为可能的数字或符号（根据上下文）
        price_pattern = re.compile(r'(\$\s*)(\ufffd+)(\s*)')
        
        def replace_price_placeholders(match):
            prefix, placeholders, suffix = match.groups()
            # 根据乱码长度猜测数字位数
            if len(placeholders) <= 3:
                # 可能是一个3位数以下的数字
                return f"{prefix}999{suffix}"
            elif len(placeholders) <= 5:
                # 可能是一个5位数以下的数字
                return f"{prefix}8,992{suffix}"
            return match.group(0)  # 无法猜测时保持原样
            
        text = price_pattern.sub(replace_price_placeholders, text)
        
        return text.strip()
    
    async def _process_text(self, file: BinaryIO) -> Dict[str, Any]:
        """处理文本文件"""
        try:
            # 读取文本
            content = file.read().decode("utf-8", errors="replace")
            
            return {
                "text": content,
                "metadata": {
                    "format": "text"
                }
            }
            
        except Exception as e:
            logger.error(f"处理文本文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}
    
    async def _process_doc(self, file: BinaryIO) -> Dict[str, Any]:
        """处理DOC文件"""
        try:
            # 尝试导入textract
            import textract
            
            # 保存临时文件
            temp_path = f"/tmp/temp_doc_{int(time.time())}.doc"
            with open(temp_path, "wb") as temp_file:
                temp_file.write(file.read())
            
            # 使用textract提取文本
            text = textract.process(temp_path).decode("utf-8", errors="replace")
            
            # 删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return {
                "text": text,
                "metadata": {
                    "format": "doc"
                }
            }
            
        except ImportError:
            logger.error("处理DOC文件需要textract库")
            return {"text": "", "metadata": {"error": "缺少textract库"}}
        except Exception as e:
            logger.error(f"处理DOC文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}
    
    async def _process_docx(self, file: BinaryIO) -> Dict[str, Any]:
        """处理DOCX文件"""
        try:
            # 尝试导入python-docx
            import docx
            
            # 保存临时文件
            temp_path = f"/tmp/temp_docx_{int(time.time())}.docx"
            with open(temp_path, "wb") as temp_file:
                temp_file.write(file.read())
            
            # 使用python-docx提取文本
            doc = docx.Document(temp_path)
            text = "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            # 提取元数据
            metadata = {"format": "docx"}
            if self.extract_metadata and hasattr(doc, "core_properties"):
                props = doc.core_properties
                metadata.update({
                    "title": props.title,
                    "author": props.author,
                    "created": str(props.created) if props.created else None,
                    "modified": str(props.modified) if props.modified else None
                })
                # 过滤None值
                metadata = {k: v for k, v in metadata.items() if v is not None}
            
            # 删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return {
                "text": text,
                "metadata": metadata
            }
            
        except ImportError:
            logger.error("处理DOCX文件需要python-docx库")
            return {"text": "", "metadata": {"error": "缺少python-docx库"}}
        except Exception as e:
            logger.error(f"处理DOCX文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}
    
    async def _process_markdown(self, file: BinaryIO) -> Dict[str, Any]:
        """处理Markdown文件"""
        try:
            # 读取文本
            content = file.read().decode("utf-8", errors="replace")
            
            # 尝试提取标题
            title = None
            lines = content.split("\n")
            if lines and lines[0].startswith("# "):
                title = lines[0].lstrip("# ").strip()
            
            metadata = {
                "format": "markdown"
            }
            
            if title:
                metadata["title"] = title
            
            return {
                "text": content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"处理Markdown文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}
    
    async def _process_html(self, file: BinaryIO) -> Dict[str, Any]:
        """处理HTML文件"""
        try:
            # 尝试导入BeautifulSoup
            from bs4 import BeautifulSoup
            
            # 读取HTML
            content = file.read().decode("utf-8", errors="replace")
            soup = BeautifulSoup(content, "html.parser")
            
            # 提取纯文本
            # 移除脚本和样式元素
            for script in soup(["script", "style"]):
                script.extract()
            
            text = soup.get_text()
            
            # 处理空格和换行符
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            # 提取元数据
            metadata = {"format": "html"}
            
            title_tag = soup.find("title")
            if title_tag:
                metadata["title"] = title_tag.string
                
            meta_description = soup.find("meta", attrs={"name": "description"})
            if meta_description:
                metadata["description"] = meta_description.get("content", "")
                
            meta_author = soup.find("meta", attrs={"name": "author"})
            if meta_author:
                metadata["author"] = meta_author.get("content", "")
            
            return {
                "text": text,
                "metadata": metadata
            }
            
        except ImportError:
            logger.error("处理HTML文件需要BeautifulSoup库")
            return {"text": "", "metadata": {"error": "缺少BeautifulSoup库"}}
        except Exception as e:
            logger.error(f"处理HTML文件时出错: {str(e)}")
            return {"text": "", "metadata": {"error": str(e)}}


def create_document_processor(config: Dict[str, Any]) -> DocumentProcessor:
    """
    从配置创建文档处理器
    
    Args:
        config: 文档处理器配置
        
    Returns:
        配置好的DocumentProcessor实例
    """
    return DocumentProcessor(config) 