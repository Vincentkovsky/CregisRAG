"""
反馈存储模块

该模块提供存储和检索用户对系统回答的反馈功能。
这些反馈可用于改进系统和评估系统性能。
"""
import os
import json
import logging
import time
from typing import List, Dict, Any, Optional, Union

# 配置日志
logger = logging.getLogger(__name__)

class FeedbackStore:
    """
    反馈存储类
    
    管理用户对系统回答的反馈。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化反馈存储
        
        Args:
            config: 配置参数
        """
        self.config = config
        
        # 从配置读取参数
        self.feedback_dir = config.get("feedback_dir", "./data/feedback")
        self.storage_type = config.get("storage_type", "file").lower()  # 'file' 或 'db'
        
        # 确保存储目录存在
        if self.storage_type == "file":
            os.makedirs(self.feedback_dir, exist_ok=True)
            
        # 数据库连接（如果使用数据库存储）
        self.db_connection = None
        
        logger.info(f"初始化反馈存储: 类型={self.storage_type}")
    
    async def initialize(self) -> bool:
        """
        初始化存储系统
        
        Returns:
            初始化是否成功
        """
        try:
            if self.storage_type == "db":
                # 这里可以添加数据库连接逻辑
                # self.db_connection = ...
                pass
                
            return True
            
        except Exception as e:
            logger.error(f"初始化反馈存储时出错: {str(e)}")
            return False
    
    async def store_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        存储用户反馈
        
        Args:
            feedback: 包含反馈信息的字典
            
        Returns:
            存储结果
        """
        try:
            # 确保反馈有必要的字段
            required_fields = ["query_id", "user_id", "rating"]
            for field in required_fields:
                if field not in feedback:
                    raise ValueError(f"反馈缺少必要字段: {field}")
            
            # 添加时间戳和ID
            feedback_id = feedback.get("feedback_id", f"feedback_{int(time.time())}_{feedback['user_id']}")
            feedback["feedback_id"] = feedback_id
            feedback["timestamp"] = feedback.get("timestamp", time.time())
            
            # 存储反馈
            if self.storage_type == "file":
                await self._store_feedback_to_file(feedback)
            elif self.storage_type == "db":
                await self._store_feedback_to_db(feedback)
            
            logger.info(f"已存储用户反馈: ID={feedback_id}")
            
            return {
                "status": "success",
                "feedback_id": feedback_id
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"存储反馈时出错: {error_msg}")
            
            return {
                "status": "failed",
                "error": error_msg
            }
    
    async def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特定反馈
        
        Args:
            feedback_id: 反馈ID
            
        Returns:
            反馈信息，如果不存在则为None
        """
        try:
            if self.storage_type == "file":
                return await self._get_feedback_from_file(feedback_id)
            elif self.storage_type == "db":
                return await self._get_feedback_from_db(feedback_id)
            
            return None
            
        except Exception as e:
            logger.error(f"获取反馈时出错: {str(e)}")
            return None
    
    async def get_feedback_for_query(self, query_id: str) -> List[Dict[str, Any]]:
        """
        获取特定查询的所有反馈
        
        Args:
            query_id: 查询ID
            
        Returns:
            反馈列表
        """
        try:
            all_feedback = await self.get_all_feedback()
            
            # 过滤指定查询的反馈
            query_feedback = [f for f in all_feedback if f.get("query_id") == query_id]
            
            return query_feedback
            
        except Exception as e:
            logger.error(f"获取查询反馈时出错: {str(e)}")
            return []
    
    async def get_all_feedback(self) -> List[Dict[str, Any]]:
        """
        获取所有反馈
        
        Returns:
            反馈列表
        """
        try:
            if self.storage_type == "file":
                return await self._get_all_feedback_from_files()
            elif self.storage_type == "db":
                return await self._get_all_feedback_from_db()
            
            return []
            
        except Exception as e:
            logger.error(f"获取所有反馈时出错: {str(e)}")
            return []
    
    async def get_feedback_stats(self) -> Dict[str, Any]:
        """
        获取反馈统计信息
        
        Returns:
            包含统计信息的字典
        """
        try:
            all_feedback = await self.get_all_feedback()
            
            if not all_feedback:
                return {
                    "total_count": 0,
                    "average_rating": 0,
                    "ratings_distribution": {}
                }
            
            # 计算总体评分
            ratings = [f.get("rating", 0) for f in all_feedback if "rating" in f]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            
            # 计算评分分布
            ratings_dist = {}
            for r in ratings:
                ratings_dist[r] = ratings_dist.get(r, 0) + 1
            
            return {
                "total_count": len(all_feedback),
                "average_rating": avg_rating,
                "ratings_distribution": ratings_dist
            }
            
        except Exception as e:
            logger.error(f"获取反馈统计时出错: {str(e)}")
            return {"error": str(e)}
    
    async def _store_feedback_to_file(self, feedback: Dict[str, Any]) -> None:
        """将反馈存储到文件"""
        file_path = os.path.join(self.feedback_dir, f"{feedback['feedback_id']}.json")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)
    
    async def _get_feedback_from_file(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """从文件获取反馈"""
        file_path = os.path.join(self.feedback_dir, f"{feedback_id}.json")
        
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    async def _get_all_feedback_from_files(self) -> List[Dict[str, Any]]:
        """从文件获取所有反馈"""
        all_feedback = []
        
        for filename in os.listdir(self.feedback_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.feedback_dir, filename)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        feedback = json.load(f)
                        all_feedback.append(feedback)
                except Exception as e:
                    logger.error(f"读取反馈文件时出错 {file_path}: {str(e)}")
        
        return all_feedback
    
    async def _store_feedback_to_db(self, feedback: Dict[str, Any]) -> None:
        """将反馈存储到数据库"""
        # 这里可以添加数据库存储逻辑
        # 目前占位使用
        pass
    
    async def _get_feedback_from_db(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取反馈"""
        # 这里可以添加数据库查询逻辑
        # 目前占位使用
        return None
    
    async def _get_all_feedback_from_db(self) -> List[Dict[str, Any]]:
        """从数据库获取所有反馈"""
        # 这里可以添加数据库查询逻辑
        # 目前占位使用
        return []


def create_feedback_store(config: Dict[str, Any]) -> FeedbackStore:
    """
    从配置创建反馈存储
    
    Args:
        config: 配置参数
        
    Returns:
        配置好的FeedbackStore实例
    """
    return FeedbackStore(config) 