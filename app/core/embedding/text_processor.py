"""
文本预处理模块

该模块提供文本清洗、分词、停用词过滤和查询扩展等功能，
用于提高嵌入质量和检索效果。
"""
import re
import os
import logging
import unicodedata
import html
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 尝试导入jieba分词
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    logger.warning("无法导入jieba分词库，中文分词功能将不可用")
    JIEBA_AVAILABLE = False

class TextProcessor:
    """
    文本预处理器
    
    提供一系列文本清洗和处理功能，用于提高嵌入质量。
    """
    
    def __init__(self, 
                remove_urls: bool = True,
                remove_html: bool = True,
                normalize_whitespace: bool = True,
                lowercase: bool = True,
                remove_punctuation: bool = False,
                segmentation_enabled: bool = True,
                remove_stopwords: bool = True,
                stopwords_file: Optional[str] = None,
                query_expansion_enabled: bool = True,
                query_rewrite_count: int = 2):
        """
        初始化文本预处理器
        
        Args:
            remove_urls: 是否移除URL
            remove_html: 是否移除HTML标签
            normalize_whitespace: 是否规范化空白字符
            lowercase: 是否转为小写
            remove_punctuation: 是否移除标点符号
            segmentation_enabled: 是否启用分词
            remove_stopwords: 是否移除停用词
            stopwords_file: 停用词文件路径
            query_expansion_enabled: 是否启用查询扩展
            query_rewrite_count: 查询重写数量
        """
        self.remove_urls = remove_urls
        self.remove_html = remove_html
        self.normalize_whitespace = normalize_whitespace
        self.lowercase = lowercase
        self.remove_punctuation = remove_punctuation
        self.segmentation_enabled = segmentation_enabled and JIEBA_AVAILABLE
        self.remove_stopwords = remove_stopwords
        self.stopwords_file = stopwords_file
        self.query_expansion_enabled = query_expansion_enabled
        self.query_rewrite_count = query_rewrite_count
        
        # 加载停用词
        self.stopwords = self.load_stopwords(stopwords_file)
        
        # 正则表达式模式
        self.url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self.html_pattern = re.compile(r'<.*?>')
        self.whitespace_pattern = re.compile(r'\s+')
        self.punctuation_pattern = re.compile(r'[^\w\s]')
        
        logger.info("文本预处理器初始化完成")
    
    def load_stopwords(self, stopwords_file: Optional[str] = None) -> Set[str]:
        """
        加载停用词
        
        Args:
            stopwords_file: 停用词文件路径
            
        Returns:
            停用词集合
        """
        stopwords = set()
        
        if not self.remove_stopwords:
            return stopwords
            
        try:
            # 尝试从文件加载停用词
            if stopwords_file:
                file_path = Path(stopwords_file)
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                stopwords.add(line)
                    logger.info(f"已从{stopwords_file}加载{len(stopwords)}个停用词")
                else:
                    logger.warning(f"停用词文件{stopwords_file}不存在")
                    
            # 如果未指定文件或文件不存在，尝试加载默认中文停用词
            if not stopwords and JIEBA_AVAILABLE:
                # 使用一些常见的中文停用词
                default_stopwords = {
                    '的', '了', '和', '是', '就', '都', '而', '及', '與', '著', '或', '一個', '沒有',
                    '我們', '你們', '他們', '她們', '自己', '其中', '一些'
                }
                stopwords.update(default_stopwords)
                logger.info(f"已加载{len(default_stopwords)}个默认中文停用词")
                
        except Exception as e:
            logger.error(f"加载停用词失败: {str(e)}")
            
        return stopwords
    
    def clean_text(self, text: str) -> str:
        """
        清洗文本
        
        Args:
            text: 输入文本
            
        Returns:
            清洗后的文本
        """
        if not text:
            return ""
            
        # 移除URL
        if self.remove_urls:
            text = self.url_pattern.sub(' ', text)
            
        # 移除HTML标签
        if self.remove_html:
            text = self.html_pattern.sub(' ', text)
            text = html.unescape(text)  # 处理HTML实体
            
        # 规范化Unicode字符
        text = unicodedata.normalize('NFKC', text)
        
        # 转为小写
        if self.lowercase:
            text = text.lower()
            
        # 移除标点符号
        if self.remove_punctuation:
            text = self.punctuation_pattern.sub(' ', text)
            
        # 规范化空白字符
        if self.normalize_whitespace:
            text = self.whitespace_pattern.sub(' ', text)
            text = text.strip()
            
        return text
    
    def process_for_embedding(self, text: str) -> str:
        """
        处理用于嵌入的文本
        
        Args:
            text: 输入文本
            
        Returns:
            处理后的文本
        """
        if not text:
            return ""
            
        # 基础清洗
        cleaned_text = self.clean_text(text)
        
        # 如果启用分词，对文本进行分词处理
        if self.segmentation_enabled and JIEBA_AVAILABLE:
            # 检测文本语言
            if self._is_chinese_text(cleaned_text):
                # 中文分词
                tokens = list(jieba.cut(cleaned_text))
                
                # 移除停用词
                if self.remove_stopwords and self.stopwords:
                    tokens = [token for token in tokens if token not in self.stopwords]
                    
                # 重新组合为文本
                cleaned_text = ' '.join(tokens)
                
        return cleaned_text
    
    def process_query(self, query: str) -> str:
        """
        处理查询文本
        
        查询文本的处理可能与文档不同，例如保留更多原始信息
        
        Args:
            query: 查询文本
            
        Returns:
            处理后的查询文本
        """
        if not query:
            return ""
            
        # 查询通常不需要移除标点
        original_remove_punctuation = self.remove_punctuation
        self.remove_punctuation = False
        
        # 基础清洗
        cleaned_query = self.clean_text(query)
        
        # 恢复设置
        self.remove_punctuation = original_remove_punctuation
        
        # 对查询进行分词，但不一定移除停用词
        if self.segmentation_enabled and JIEBA_AVAILABLE and self._is_chinese_text(cleaned_query):
            # 中文分词
            tokens = list(jieba.cut(cleaned_query))
            
            # 对于查询，可能希望保留停用词，以保持语义完整
            # 或者更有选择性地移除停用词
            if self.remove_stopwords and self.stopwords:
                # 提取查询中的关键词，可以采用更复杂的算法
                key_terms = self._extract_key_terms(cleaned_query, tokens)
                
                # 只有当关键词足够多时，才移除停用词
                if len(key_terms) >= 2:
                    tokens = [token for token in tokens if token not in self.stopwords or token in key_terms]
            
            # 重新组合为文本
            cleaned_query = ' '.join(tokens)
            
        return cleaned_query
    
    def expand_query(self, query: str) -> List[str]:
        """
        扩展查询，生成查询的多个变体
        
        Args:
            query: 原始查询
            
        Returns:
            查询变体列表
        """
        if not query or not self.query_expansion_enabled:
            return [query]
            
        variants = [query]  # 始终包含原始查询
        
        # 清洗后的查询也作为一个变体
        cleaned_query = self.process_query(query)
        if cleaned_query != query:
            variants.append(cleaned_query)
        
        # 提取关键短语
        key_phrases = self._extract_key_phrases(query)
        for phrase in key_phrases:
            if phrase not in variants:
                variants.append(phrase)
        
        # 限制变体数量
        return variants[:self.query_rewrite_count + 1]  # +1是因为包含原始查询
    
    def _is_chinese_text(self, text: str) -> bool:
        """
        检测文本是否主要为中文
        
        Args:
            text: 输入文本
            
        Returns:
            是否为中文文本
        """
        # 中文字符范围
        chinese_chars = 0
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 基本汉字范围
                chinese_chars += 1
                
        # 如果中文字符占比超过一定阈值，则认为是中文文本
        return chinese_chars > 0 and chinese_chars / max(len(text), 1) > 0.1
    
    def _extract_key_terms(self, text: str, tokens: List[str]) -> Set[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            tokens: 分词结果
            
        Returns:
            关键词集合
        """
        # 简单方法：选择长度大于1的词
        # 在实际应用中，可以使用TF-IDF或其他关键词提取算法
        key_terms = {token for token in tokens if len(token) > 1}
        
        return key_terms
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """
        从文本中提取关键短语
        
        Args:
            text: 输入文本
            
        Returns:
            关键短语列表
        """
        phrases = []
        
        # 如果是中文文本且可用jieba
        if self._is_chinese_text(text) and JIEBA_AVAILABLE:
            # 使用jieba的关键词提取
            try:
                import jieba.analyse
                # 提取前N个关键词
                keywords = jieba.analyse.extract_tags(text, topK=min(5, len(text)//2 + 1))
                # 构建关键短语
                if len(keywords) >= 2:
                    phrases.append(' '.join(keywords))
            except Exception as e:
                logger.error(f"使用jieba提取关键词失败: {str(e)}")
        
        # 基于规则的简单变化
        # 例如，移除常见的疑问词
        question_words = {'什么', '如何', '怎么', '为什么', '哪里', '何时', '是否'}
        
        cleaned_text = text
        for word in question_words:
            if word in text:
                cleaned_text = text.replace(word, '').strip()
                if cleaned_text and cleaned_text != text:
                    phrases.append(cleaned_text)
                break
        
        return phrases


def create_text_processor(config: Dict[str, Any]) -> TextProcessor:
    """
    从配置创建文本预处理器
    
    Args:
        config: 文本预处理器配置
        
    Returns:
        文本预处理器实例
    """
    return TextProcessor(
        remove_urls=config.get("remove_urls", True),
        remove_html=config.get("remove_html", True),
        normalize_whitespace=config.get("normalize_whitespace", True),
        lowercase=config.get("lowercase", True),
        remove_punctuation=config.get("remove_punctuation", False),
        segmentation_enabled=config.get("segmentation_enabled", True),
        remove_stopwords=config.get("remove_stopwords", True),
        stopwords_file=config.get("stopwords_file"),
        query_expansion_enabled=config.get("query_expansion_enabled", True),
        query_rewrite_count=config.get("query_rewrite_count", 2)
    ) 