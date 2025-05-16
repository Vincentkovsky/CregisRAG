"""
CregisRAG API 主入口文件
"""
import yaml
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

# 导入环境变量加载工具
from app.utils.env_loader import load_api_keys, process_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 加载环境变量中的API密钥
api_keys = load_api_keys()
if api_keys:
    logger.info(f"已加载 {len(api_keys)} 个API密钥")
else:
    logger.warning("未加载任何API密钥，请确保.env文件配置正确")

# 加载配置
def load_config():
    config_path = Path("config.yml")
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
        # 处理配置中的环境变量引用
        return process_config(config)

config = load_config()

# 创建FastAPI应用
app = FastAPI(
    title=config["frontend"]["title"],
    description=config["frontend"]["description"],
    version="0.1.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["app"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "内部服务器错误"},
    )

# 根路径端点
@app.get("/", response_class=HTMLResponse)
async def root():
    """
    应用根路径，返回简单的HTML页面
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CregisRAG - 智能检索增强生成系统</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #333;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }
            h2 {
                color: #444;
                margin-top: 30px;
            }
            code {
                background-color: #f4f4f4;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: monospace;
            }
            .endpoint {
                background-color: #f9f9f9;
                border-left: 4px solid #ddd;
                padding: 10px 15px;
                margin: 10px 0;
            }
            .method {
                font-weight: bold;
                color: #0366d6;
            }
        </style>
    </head>
    <body>
        <h1>CregisRAG - 智能检索增强生成系统</h1>
        <p>欢迎使用CregisRAG，这是一个强大的检索增强生成（RAG）系统，可以帮助你基于自己的知识库构建智能问答应用。</p>
        
        <h2>API文档</h2>
        <p>完整的API文档可以在 <a href="/docs">/docs</a> 或 <a href="/redoc">/redoc</a> 访问。</p>
        
        <h2>主要功能</h2>
        <ul>
            <li>文档上传和知识库构建</li>
            <li>智能查询和回答生成</li>
            <li>基于上下文的精确回答</li>
            <li>完整的源文档引用</li>
            <li>系统状态监控和管理</li>
        </ul>
        
        <h2>主要API端点</h2>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/ingest/upload</code> - 上传文档文件
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/ingest/url</code> - 从URL导入内容
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/query</code> - 查询知识库
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/ingest/documents</code> - 获取所有文档
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/admin/status</code> - 获取系统状态
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/health</code> - 健康检查
        </div>
    </body>
    </html>
    """
    return html_content

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "健康", "version": "0.1.0"}

# 导入和包含API路由
from app.api.routes import query, ingest, admin

# 注册路由
app.include_router(query.router, prefix="/api", tags=["查询"])
app.include_router(ingest.router, prefix="/api", tags=["数据摄取"])
app.include_router(admin.router, prefix="/api", tags=["管理"])

# 挂载静态文件
static_dir = Path("frontend/build")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
@app.on_event("startup")
async def startup_event():
    logger.info("API服务正在启动...")
    # 在这里可以添加启动时需要执行的代码，例如：
    # - 初始化数据库连接
    # - 预加载模型
    # - 启动后台任务

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API服务正在关闭...")
    # 在这里可以添加关闭时需要执行的代码，例如：
    # - 关闭数据库连接
    # - 保存缓存 