"""
LLM生成服务模块

该模块提供大型语言模型生成功能，支持多种提供商和模型。
"""
import logging
import time
from typing import List, Dict, Any, Optional, Union
import os
import re

# 配置日志
logger = logging.getLogger(__name__)

def replace_env_vars(value: str) -> str:
    """替换字符串中的环境变量引用"""
    if not isinstance(value, str):
        return value
        
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

class LLMService:
    """
    LLM服务类
    
    提供与大型语言模型交互的接口，支持多个提供商。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM服务
        
        Args:
            config: 包含配置参数的字典
        """
        self.config = config.copy()  # 创建配置的副本，以便可以修改
        
        # 处理config中的环境变量引用
        if "api_key" in self.config and isinstance(self.config["api_key"], str):
            self.config["api_key"] = replace_env_vars(self.config["api_key"])
        
        # 读取配置
        self.provider = self.config.get("provider", "openai").lower()
        self.model_name = self.config.get("model", self.config.get("model_name", "gpt-4-turbo"))
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 2000)
        self.timeout = self.config.get("timeout", 60)
        
        # 初始化客户端为None
        self.client = None
        
        # 验证配置
        self._validate_config()
        
        logger.info(f"初始化LLM服务: 提供商={self.provider}, 模型={self.model_name}")
    
    def _validate_config(self):
        """验证配置参数"""
        # 确保温度在合理范围内
        if not 0 <= self.temperature <= 1.0:
            logger.warning(f"温度设置 {self.temperature} 超出范围 0-1，已调整为0.7")
            self.temperature = 0.7
            
        # 确保最大令牌数是正数
        if self.max_tokens <= 0:
            logger.warning(f"最大令牌数 {self.max_tokens} 无效，已调整为2000")
            self.max_tokens = 2000
    
    async def initialize(self) -> bool:
        """
        初始化LLM客户端
        
        Returns:
            初始化是否成功
        """
        try:
            if self.provider == "openai":
                from openai import AsyncOpenAI
                
                api_key = self.config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
                api_base = self.config.get("api_base")
                
                if not api_key:
                    raise ValueError("使用OpenAI服务需要API密钥")
                
                self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
                logger.info("初始化OpenAI LLM服务成功")
                
            elif self.provider == "anthropic":
                import anthropic
                
                api_key = self.config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
                
                if not api_key:
                    raise ValueError("使用Anthropic服务需要API密钥")
                
                self.client = anthropic.AsyncAnthropic(api_key=api_key)
                logger.info("初始化Anthropic LLM服务成功")
                
            elif self.provider == "deepseek":
                from openai import AsyncOpenAI
                
                api_key = self.config.get("api_key", os.environ.get("DEEPSEEK_API_KEY", ""))
                api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
                
                if not api_key:
                    raise ValueError("使用DeepSeek服务需要API密钥")
                
                # 安全记录日志，不展示API密钥
                logger.info("已获取DeepSeek API密钥")
                self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
                logger.info(f"初始化DeepSeek LLM服务成功, 模型: {self.model_name}")
            
            elif self.provider == "zhipuai":
                # 使用ZhipuAI的LLM服务
                try:
                    import asyncio
                    from zhipuai import ZhipuAI
                    
                    api_key = self.config.get("api_key", os.environ.get("ZHIPUAI_API_KEY", ""))
                    
                    if not api_key:
                        raise ValueError("使用智谱AI服务需要API密钥")
                    
                    logger.info("已获取智谱AI API密钥")
                    self.client = ZhipuAI(api_key=api_key)
                    logger.info(f"初始化智谱AI LLM服务成功, 模型: {self.model_name}")
                except ImportError:
                    logger.error("使用智谱AI需要安装zhipuai库，请使用pip install zhipuai安装")
                    return False
                
            elif self.provider == "local":
                # 这里可以添加本地模型支持，如使用llama.cpp或llama-cpp-python
                # 目前仅做占位使用
                pass
                
            else:
                raise ValueError(f"不支持的LLM提供商: {self.provider}")
            
            logger.info(f"LLM服务初始化成功: {self.provider}")
            return True
            
        except Exception as e:
            logger.error(f"LLM服务初始化失败: {str(e)}")
            return False
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        使用LLM生成文本
        
        Args:
            prompt: 提示文本
            system_message: 系统消息（指令）
            temperature: 生成温度，值越高结果越随机
            max_tokens: 生成的最大令牌数
            stop_sequences: 停止生成的序列列表
            
        Returns:
            包含生成文本和元数据的字典
        """
        if not self.client:
            raise ValueError("LLM客户端未初始化")
        
        # 使用传入的参数，如果没有则使用默认值
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        start_time = time.time()
        logger.info(f"开始LLM生成: 模型={self.model_name}, 温度={temperature}")
        
        try:
            response = None
            
            if self.provider == "openai":
                response = await self._generate_with_openai(
                    prompt, 
                    system_message, 
                    temperature, 
                    max_tokens, 
                    stop_sequences
                )
                
            elif self.provider == "anthropic":
                response = await self._generate_with_anthropic(
                    prompt, 
                    system_message, 
                    temperature, 
                    max_tokens, 
                    stop_sequences
                )
                
            elif self.provider == "deepseek":
                # DeepSeek使用与OpenAI兼容的API
                response = await self._generate_with_openai(
                    prompt, 
                    system_message, 
                    temperature, 
                    max_tokens, 
                    stop_sequences
                )
                
            elif self.provider == "zhipuai":
                response = await self._generate_with_zhipuai(
                    prompt, 
                    system_message, 
                    temperature, 
                    max_tokens, 
                    stop_sequences
                )
                
            elif self.provider == "local":
                # 本地模型生成逻辑
                response = {"text": "本地模型生成的响应", "model": "local-model"}
                
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
                
            generation_time = time.time() - start_time
            logger.info(f"LLM生成完成, 耗时: {generation_time:.2f}秒")
            
            # 添加通用元数据
            response.update({
                "provider": self.provider,
                "model": self.model_name,
                "processing_time": generation_time
            })
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM生成错误: {error_msg}")
            
            # 返回错误信息
            return {
                "text": f"生成过程中出错: {error_msg}",
                "error": error_msg,
                "provider": self.provider,
                "model": self.model_name,
                "processing_time": time.time() - start_time
            }
    
    async def _generate_with_openai(self,
                                   prompt: str,
                                   system_message: Optional[str],
                                   temperature: float,
                                   max_tokens: int,
                                   stop_sequences: Optional[List[str]]) -> Dict[str, Any]:
        """使用OpenAI API生成文本"""
        messages = []
        
        # 添加系统消息
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # 添加用户消息
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences,
                timeout=self.timeout
            )
            
            # 提取响应文本
            if response.choices and len(response.choices) > 0:
                text = response.choices[0].message.content or ""
                
                return {
                    "text": text,
                    "finish_reason": response.choices[0].finish_reason,
                    "tokens": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            else:
                return {"text": "", "error": "响应中没有选择"}
                
        except Exception as e:
            logger.error(f"OpenAI API错误: {str(e)}")
            raise
    
    async def _generate_with_anthropic(self,
                                      prompt: str,
                                      system_message: Optional[str],
                                      temperature: float,
                                      max_tokens: int,
                                      stop_sequences: Optional[List[str]]) -> Dict[str, Any]:
        """使用Anthropic API生成文本"""
        try:
            # 构建Anthropic消息
            messages = [{"role": "user", "content": prompt}]
            
            # 创建Anthropic消息
            response = await self.client.messages.create(
                model=self.model_name,
                messages=messages,
                system=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                stop_sequences=stop_sequences
            )
            
            # 提取响应文本
            if response.content and len(response.content) > 0:
                # 获取文本部分
                text_blocks = [block.text for block in response.content if block.type == "text"]
                text = "\n".join(text_blocks)
                
                return {
                    "text": text,
                    "stop_reason": response.stop_reason,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            else:
                return {"text": "", "error": "响应中没有内容"}
                
        except Exception as e:
            logger.error(f"Anthropic API错误: {str(e)}")
            raise

    async def _generate_with_zhipuai(self,
                                     prompt: str,
                                     system_message: Optional[str],
                                     temperature: float,
                                     max_tokens: int,
                                     stop_sequences: Optional[List[str]]) -> Dict[str, Any]:
        """使用智谱AI API生成文本"""
        try:
            import asyncio
            
            messages = []
            
            # 添加系统消息
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # 添加用户消息
            messages.append({"role": "user", "content": prompt})
            
            # 构建请求参数
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # 如果有停止序列，添加stop参数
            if stop_sequences:
                params["stop"] = stop_sequences
                
            # 使用线程池执行同步API调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.client.chat.completions.create(**params)
            )
            
            # 提取响应文本
            if response.choices and len(response.choices) > 0:
                text = response.choices[0].message.content or ""
                
                return {
                    "text": text,
                    "finish_reason": response.choices[0].finish_reason,
                    "tokens": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            else:
                return {"text": "", "error": "响应中没有选择"}
                
        except Exception as e:
            logger.error(f"智谱AI API错误: {str(e)}")
            raise


def create_llm_service(config: Dict[str, Any]) -> LLMService:
    """
    从配置创建LLM服务
    
    Args:
        config: LLM服务配置
        
    Returns:
        配置好的LLMService实例
    """
    return LLMService(config) 