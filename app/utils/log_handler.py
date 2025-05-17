"""
日志处理工具

用于记录和检索查询日志和错误日志
"""
import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)

class LogHandler:
    """日志处理类，负责记录查询和错误日志"""
    
    def __init__(self, base_dir: str = "./data/logs"):
        """
        初始化日志处理器
        
        Args:
            base_dir: 日志存储的基础目录
        """
        self.base_dir = base_dir
        self.queries_dir = os.path.join(base_dir, "queries")
        self.errors_dir = os.path.join(base_dir, "errors")
        
        # 确保目录存在
        os.makedirs(self.queries_dir, exist_ok=True)
        os.makedirs(self.errors_dir, exist_ok=True)
        
        logger.info(f"日志处理器初始化: 查询日志目录={self.queries_dir}, 错误日志目录={self.errors_dir}")
    
    def log_query(self, data: Dict[str, Any]) -> bool:
        """
        记录查询日志
        
        Args:
            data: 包含查询信息的字典
            
        Returns:
            操作是否成功
        """
        try:
            timestamp = data.get("timestamp", time.time())
            query_id = data.get("query_id", f"q_{int(timestamp)}")
            
            # 构造文件名
            file_name = f"{query_id}.json"
            file_path = os.path.join(self.queries_dir, file_name)
            
            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"查询日志已记录: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"记录查询日志时出错: {str(e)}")
            return False
    
    def log_error(self, data: Dict[str, Any]) -> bool:
        """
        记录错误日志
        
        Args:
            data: 包含错误信息的字典
            
        Returns:
            操作是否成功
        """
        try:
            timestamp = data.get("timestamp", time.time())
            error_id = data.get("error_id", f"e_{int(timestamp)}")
            
            # 构造文件名
            file_name = f"{error_id}.json"
            file_path = os.path.join(self.errors_dir, file_name)
            
            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"错误日志已记录: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"记录错误日志时出错: {str(e)}")
            return False
    
    def get_recent_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的查询记录
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            查询记录列表
        """
        try:
            queries = []
            
            # 列出所有查询日志文件
            files = os.listdir(self.queries_dir)
            files = [f for f in files if f.endswith(".json")]
            
            # 按文件修改时间排序，最新的在前面
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.queries_dir, x)), reverse=True)
            
            # 读取最新的查询
            for file_name in files[:limit]:
                file_path = os.path.join(self.queries_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        query_data = json.load(f)
                        queries.append(query_data)
                except Exception as e:
                    logger.warning(f"读取查询日志文件时出错: {file_path}, {str(e)}")
                    continue
            
            return queries
            
        except Exception as e:
            logger.error(f"获取最近查询记录时出错: {str(e)}")
            return []
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的错误记录
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            错误记录列表
        """
        try:
            errors = []
            
            # 列出所有错误日志文件
            files = os.listdir(self.errors_dir)
            files = [f for f in files if f.endswith(".json")]
            
            # 按文件修改时间排序，最新的在前面
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.errors_dir, x)), reverse=True)
            
            # 读取最新的错误
            for file_name in files[:limit]:
                file_path = os.path.join(self.errors_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        error_data = json.load(f)
                        errors.append(error_data)
                except Exception as e:
                    logger.warning(f"读取错误日志文件时出错: {file_path}, {str(e)}")
                    continue
            
            return errors
            
        except Exception as e:
            logger.error(f"获取最近错误记录时出错: {str(e)}")
            return []
    
    def get_query_stats(self) -> Dict[str, Any]:
        """
        获取查询统计信息
        
        Returns:
            查询统计信息
        """
        try:
            stats = {
                "total_queries": 0,
                "queries_last_24h": 0,
                "avg_query_time": 0,
                "avg_tokens_per_query": 0,
            }
            
            # 列出所有查询日志文件
            files = os.listdir(self.queries_dir)
            files = [f for f in files if f.endswith(".json")]
            
            # 计算总查询数
            stats["total_queries"] = len(files)
            
            # 计算24小时内的查询数和平均查询时间
            cutoff_time = time.time() - (24 * 60 * 60)  # 24小时前的时间戳
            recent_queries = []
            total_time = 0
            total_tokens = 0
            
            for file_name in files:
                file_path = os.path.join(self.queries_dir, file_name)
                file_time = os.path.getmtime(file_path)
                
                if file_time >= cutoff_time:
                    stats["queries_last_24h"] += 1
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            query_data = json.load(f)
                            recent_queries.append(query_data)
                            
                            # 累加处理时间
                            processing_time = query_data.get("processing_time", 0)
                            total_time += processing_time
                            
                            # 累加token使用量
                            tokens = query_data.get("token_usage", {}).get("total_tokens", 0)
                            total_tokens += tokens
                    except Exception:
                        pass
            
            # 计算平均值
            if recent_queries:
                stats["avg_query_time"] = round(total_time / len(recent_queries), 2)
                stats["avg_tokens_per_query"] = round(total_tokens / len(recent_queries), 0)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取查询统计信息时出错: {str(e)}")
            return {
                "total_queries": 0,
                "queries_last_24h": 0,
                "avg_query_time": 0,
                "avg_tokens_per_query": 0,
            }

# 创建一个全局的日志处理器实例
log_handler = LogHandler()

# 辅助函数 - 记录查询
def record_query(query: str, answer: str, sources: List[Dict[str, Any]], processing_time: float, token_usage: Dict[str, int] = None) -> None:
    """记录一次查询"""
    data = {
        "timestamp": time.time(),
        "query_text": query,
        "answer": answer,
        "sources": sources,
        "processing_time": processing_time,
        "token_usage": token_usage or {},
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    log_handler.log_query(data)

# 辅助函数 - 记录错误
def record_error(error_type: str, message: str, component: str, details: Optional[Dict[str, Any]] = None) -> None:
    """记录一个错误"""
    data = {
        "timestamp": time.time(),
        "error_type": error_type,
        "message": message,
        "component": component,
        "details": details or {},
        "error_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    log_handler.log_error(data) 