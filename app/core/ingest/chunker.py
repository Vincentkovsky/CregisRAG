"""
文本分块器

该模块负责将长文本分割成适合嵌入的较小文本块。
不同的分块策略适用于不同类型的文档和用例。
"""
import re
import logging
from typing import List, Dict, Any, Optional, Callable

# 配置日志
logger = logging.getLogger(__name__)

class TextChunker:
    """
    文本分块器类
    
    将长文本文档分割成适合向量化和检索的较小文本块。
    支持多种分块策略。
    """
    
    def __init__(
        self, 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200,
        split_method: str = "paragraph",
        min_chunk_size: int = 100
    ):
        """
        初始化文本分块器
        
        Args:
            chunk_size: 每个块的目标大小（字符数）
            chunk_overlap: 相邻块之间的重叠大小（字符数）
            split_method: 分块策略 ("paragraph", "sentence", "fixed", "recursive")
            min_chunk_size: 最小块大小，小于此大小的块会与其他块合并
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.split_method = split_method
        self.min_chunk_size = min_chunk_size
        
        # 分块策略映射
        self.split_methods = {
            "paragraph": self._split_by_paragraph,
            "sentence": self._split_by_sentence,
            "fixed": self._split_by_fixed_size,
            "recursive": self._split_recursive
        }
        
        if split_method not in self.split_methods:
            raise ValueError(f"不支持的分块方法: {split_method}。支持的方法: {list(self.split_methods.keys())}")
        
        logger.info(f"初始化文本分块器: 方法={split_method}, 块大小={chunk_size}, 重叠={chunk_overlap}")
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        将文本分块
        
        Args:
            text: 待分块的文本
            metadata: 要应用于所有块的元数据
            
        Returns:
            包含文本块和元数据的字典列表
        """
        if not text or not text.strip():
            logger.warning("收到空文本进行分块")
            return []
        
        # 使用选定的方法分块
        split_method = self.split_methods[self.split_method]
        chunks = split_method(text)
        
        # 确保元数据存在
        metadata = metadata or {}
        
        # 将每个文本块与其元数据组合
        chunk_dicts = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():  # 跳过空块
                continue
                
            # 复制元数据并添加块特定信息
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "chunk_count": len(chunks)
            })
            
            chunk_dicts.append({
                "text": chunk,
                "metadata": chunk_metadata
            })
        
        logger.info(f"文本分块完成: 输入长度={len(text)}, 生成块数={len(chunk_dicts)}")
        return chunk_dicts
    
    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并小于最小块大小的块"""
        if not chunks:
            return []
            
        result = []
        current_chunk = chunks[0]
        
        for chunk in chunks[1:]:
            # 如果当前累积块加上下一个块仍然小于块大小，则合并
            if len(current_chunk) + len(chunk) <= self.chunk_size:
                current_chunk += "\n" + chunk
            else:
                # 如果当前块达到最小大小，则添加到结果中
                if len(current_chunk) >= self.min_chunk_size:
                    result.append(current_chunk)
                # 开始新的块
                current_chunk = chunk
        
        # 添加最后一个块
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            result.append(current_chunk)
        elif current_chunk and result:
            # 如果最后一个块太小，尝试合并到前一个块
            result[-1] += "\n" + current_chunk
            
        return result
    
    def _split_by_paragraph(self, text: str) -> List[str]:
        """按段落分块，然后处理大段落"""
        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        
        # 处理长段落
        chunks = []
        for para in paragraphs:
            if len(para) <= self.chunk_size:
                chunks.append(para)
            else:
                # 长段落使用固定大小分块
                chunks.extend(self._split_by_fixed_size(para))
        
        # 合并小块
        return self._merge_small_chunks(chunks)
    
    def _split_by_sentence(self, text: str) -> List[str]:
        """按句子分块"""
        # 简单句子分割模式
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # 如果添加这个句子会超过块大小，并且当前块不为空
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # 新块从前一个块的末尾开始（实现重叠）
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + sentence
            else:
                current_chunk += sentence + " "
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        # 合并小块
        return self._merge_small_chunks(chunks)
    
    def _split_by_fixed_size(self, text: str) -> List[str]:
        """按固定大小分块"""
        chunks = []
        
        # 每个块从前一个块末尾减去重叠部分的位置开始
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            # 确保不会越界
            chunk_end = min(i + self.chunk_size, len(text))
            # 收集块
            chunks.append(text[i:chunk_end])
            # 如果已经处理完文本，退出循环
            if chunk_end == len(text):
                break
                
        # 对于固定大小分块，我们不需要合并小块
        return chunks
    
    def _split_recursive(self, text: str) -> List[str]:
        """递归分块（适用于层次化文档）"""
        # 实现简单版本的递归分块
        # 首先按章节/标题分块
        section_pattern = r'(?=\n#+\s+)'  # Markdown标题
        sections = re.split(section_pattern, text)
        
        chunks = []
        for section in sections:
            if len(section) <= self.chunk_size:
                chunks.append(section)
            else:
                # 如果章节太长，按段落分块
                chunks.extend(self._split_by_paragraph(section))
                
        # 合并小块
        return self._merge_small_chunks(chunks)


# 辅助函数

def create_chunker_from_config(config: Dict[str, Any]) -> TextChunker:
    """
    从配置创建文本分块器实例
    
    Args:
        config: 包含分块器配置的字典
        
    Returns:
        配置的TextChunker实例
    """
    chunker_config = config.get("ingest", {}).get("chunker", {})
    
    return TextChunker(
        chunk_size=chunker_config.get("chunk_size", 1000),
        chunk_overlap=chunker_config.get("chunk_overlap", 200),
        split_method=chunker_config.get("split_by", "paragraph"),
        min_chunk_size=chunker_config.get("min_chunk_size", 100)
    ) 