"""
环境变量加载工具

用于从.env文件加载环境变量，用于加载API密钥等敏感信息
"""
import os
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any, Union

logger = logging.getLogger(__name__)

def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """
    从指定的.env文件加载环境变量
    
    Args:
        env_file: .env文件的路径
        
    Returns:
        加载的环境变量字典
    """
    env_vars = {}
    env_path = Path(env_file)
    
    if not env_path.exists():
        logger.warning(f"环境变量文件 {env_file} 不存在")
        return env_vars
    
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                    
                # 解析变量
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 去除引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                        
                    env_vars[key] = value
        
        logger.info(f"从 {env_file} 成功加载了 {len(env_vars)} 个环境变量")
        return env_vars
        
    except Exception as e:
        logger.error(f"加载环境变量文件 {env_file} 时出错: {str(e)}")
        return env_vars

def set_env_vars(env_vars: Dict[str, str]) -> None:
    """
    将环境变量字典设置到系统环境变量
    
    Args:
        env_vars: 包含环境变量的字典
    """
    for key, value in env_vars.items():
        os.environ[key] = value
    
    logger.info(f"已设置 {len(env_vars)} 个环境变量")

def get_api_key(provider: str) -> Optional[str]:
    """
    获取指定提供商的API密钥
    
    Args:
        provider: 提供商名称 (openai, deepseek, zhipuai等)
        
    Returns:
        API密钥或None (如果未找到)
    """
    provider = provider.upper()
    key_name = f"{provider}_API_KEY"
    
    # 首先尝试从环境变量获取
    api_key = os.environ.get(key_name)
    
    if not api_key:
        logger.warning(f"未找到 {provider} 的API密钥环境变量 ({key_name})")
    
    return api_key

def load_api_keys(env_file: str = ".env") -> Dict[str, str]:
    """
    从.env文件加载所有API密钥
    
    Args:
        env_file: .env文件的路径
        
    Returns:
        包含所有API密钥的字典
    """
    env_vars = load_env_file(env_file)
    api_keys = {}
    
    # 过滤出API密钥相关的环境变量
    for key, value in env_vars.items():
        if key.endswith("_API_KEY"):
            api_keys[key] = value
    
    # 设置到环境变量
    set_env_vars(env_vars)
    
    return api_keys

def process_env_vars(value: Any) -> Any:
    """
    处理配置中的环境变量引用
    
    替换形如 ${ENV_VAR} 的字符串为实际的环境变量值
    
    Args:
        value: 可能包含环境变量引用的值
        
    Returns:
        处理后的值
    """
    if isinstance(value, str):
        # 使用正则表达式匹配 ${...} 模式
        pattern = r'\${([A-Za-z0-9_]+)}'
        
        def replace_env_var(match):
            env_var_name = match.group(1)
            env_var_value = os.environ.get(env_var_name)
            if env_var_value is None:
                logger.warning(f"环境变量 {env_var_name} 未定义")
                return match.group(0)  # 如果未定义则保持原样
            return env_var_value
        
        return re.sub(pattern, replace_env_var, value)
    
    elif isinstance(value, dict):
        return {k: process_env_vars(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [process_env_vars(item) for item in value]
    
    return value

def process_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理配置字典中的所有环境变量引用
    
    Args:
        config: 配置字典
        
    Returns:
        处理后的配置字典
    """
    return process_env_vars(config) 