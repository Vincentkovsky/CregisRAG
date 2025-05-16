"""
LLM生成服务模块

该模块提供大型语言模型生成功能，支持多种提供商和模型。
"""
import logging
import time
from typing import List, Dict, Any, Optional, Union

# 配置日志
logger = logging.getLogger(__name__)

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
        self.config = config
        self.client = None
        
        # 读取配置
        self.provider = config.get("provider", "openai").lower()
        self.model_name = config.get("model_name", "gpt-4-turbo")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 2000)
        self.timeout = config.get("timeout", 60)
        
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
                
                api_key = self.config.get("api_key")
                api_base = self.config.get("api_base")
                
                if not api_key:
                    raise ValueError("使用OpenAI服务需要API密钥")
                
                self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)
                
            elif self.provider == "anthropic":
                import anthropic
                
                api_key = self.config.get("api_key")
                
                if not api_key:
                    raise ValueError("使用Anthropic服务需要API密钥")
                
                self.client = anthropic.AsyncAnthropic(api_key=api_key)
                
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


def create_llm_service(config: Dict[str, Any]) -> LLMService:
    """
    从配置创建LLM服务
    
    Args:
        config: LLM服务配置
        
    Returns:
        配置好的LLMService实例
    """
    return LLMService(config) 