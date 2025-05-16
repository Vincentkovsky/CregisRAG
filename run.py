#!/usr/bin/env python3
"""
CregisRAG - 主启动脚本
"""
import argparse
import os
import sys
import yaml
import uvicorn
from pathlib import Path


def load_config(config_path="config.yml"):
    """加载配置文件"""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"错误: 无法加载配置文件: {e}")
        sys.exit(1)


def setup_environment(config):
    """设置环境变量"""
    # 设置必要的环境变量
    os.environ["CREGIS_ENV"] = config["app"]["environment"]
    
    # 如果使用OpenAI，设置API密钥
    if config["llm"]["provider"] == "openai" and config["llm"]["openai"]["api_key"]:
        os.environ["OPENAI_API_KEY"] = config["llm"]["openai"]["api_key"]
    
    # 如果使用Anthropic，设置API密钥
    if config["llm"]["provider"] == "anthropic" and config["llm"]["anthropic"]["api_key"]:
        os.environ["ANTHROPIC_API_KEY"] = config["llm"]["anthropic"]["api_key"]
    
    # 如果使用Pinecone，设置API密钥
    if (config["vectordb"]["provider"] == "pinecone" and 
        config["vectordb"]["pinecone"]["api_key"]):
        os.environ["PINECONE_API_KEY"] = config["vectordb"]["pinecone"]["api_key"]
        os.environ["PINECONE_ENVIRONMENT"] = config["vectordb"]["pinecone"]["environment"]


def setup_directories(config):
    """创建必要的目录"""
    directories = [
        config["storage"]["data_dir"],
        config["storage"]["raw_dir"],
        config["storage"]["processed_dir"],
        config["storage"]["embeddings_dir"]
    ]
    
    # 如果使用Chroma并且需要持久化
    if (config["vectordb"]["provider"] == "chroma" and 
        "persist_directory" in config["vectordb"]["chroma"]):
        directories.append(config["vectordb"]["chroma"]["persist_directory"])
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"确保目录存在: {directory}")


def run_app(host, port, reload=False):
    """启动FastAPI应用"""
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CregisRAG - 智能检索增强生成系统")
    parser.add_argument("--config", "-c", default="config.yml", help="配置文件路径")
    parser.add_argument("--reload", "-r", action="store_true", help="启用热重载（开发模式）")
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 设置环境和目录
    setup_environment(config)
    setup_directories(config)
    
    # 启动服务
    print(f"启动CregisRAG服务于 {config['app']['host']}:{config['app']['port']}...")
    run_app(
        host=config["app"]["host"],
        port=config["app"]["port"],
        reload=args.reload or config["app"]["debug"]
    )


if __name__ == "__main__":
    main() 