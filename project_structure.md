# CregisRAG 项目结构

```
CregisRAG/
│
├── README.md                  # 项目说明文档
├── .env                       # 环境变量配置
├── .gitignore                 # Git忽略文件
├── requirements.txt           # Python依赖列表
├── config.yml                 # 项目配置文件
├── run.py                     # 主启动脚本
├── project_structure.md       # 项目结构文档
│
├── app/                       # 应用核心代码
│   ├── __init__.py
│   ├── api/                   # API接口层
│   │   ├── __init__.py
│   │   ├── main.py            # 主API入口
│   │   └── routes/            # API路由定义
│   │
│   ├── core/                  # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── rag_engine.py      # RAG引擎核心
│   │   │
│   │   ├── ingest/            # 数据摄取模块
│   │   │   └── __init__.py
│   │   │
│   │   ├── embedding/         # 向量化模块
│   │   │   ├── __init__.py
│   │   │   ├── embedding_service.py  # 嵌入服务
│   │   │   └── text_processor.py     # 文本处理
│   │   │
│   │   ├── retrieval/         # 检索模块
│   │   │   ├── __init__.py
│   │   │   └── vector_store.py       # 向量存储实现
│   │   │
│   │   ├── generation/        # 生成模块
│   │   │   └── __init__.py
│   │   │
│   │   ├── storage/           # 存储模块
│   │   │   └── __init__.py
│   │   │
│   │   └── feedback/          # 反馈处理模块
│   │       └── __init__.py
│   │
│   ├── services/              # 外部服务集成
│   │   └── __init__.py
│   │
│   ├── utils/                 # 通用工具函数
│   │   └── __init__.py
│   │
│   └── config/                # 配置加载模块
│       └── __init__.py
│
├── logs/                      # 日志目录
│   ├── app.log                # 应用日志
│   └── startup.log            # 启动日志
│
├── data/                      # 数据目录
│   ├── raw/                   # 原始数据
│   ├── processed/             # 处理后数据
│   ├── embeddings/            # 嵌入向量
│   ├── documents/             # 文档存储
│   ├── chroma/                # Chroma数据库
│   ├── logs/                  # 数据日志
│   ├── status/                # 状态信息
│   ├── stopwords/             # 停用词
│   ├── cache/                 # 缓存数据
│   └── test/                  # 测试数据
│
└── frontend/                  # 前端代码
    ├── package.json           # NPM配置
    ├── package-lock.json      # NPM依赖锁
    ├── public/                # 静态资源
    ├── build/                 # 构建输出
    │
    └── src/                   # 源代码
        ├── index.js           # 入口文件
        ├── App.js             # 主应用组件
        ├── components/        # UI组件
        ├── pages/             # 页面组件
        │   ├── Dashboard.js   # 系统仪表盘
        │   ├── Documents.js   # 文档管理
        │   ├── Home.js        # 首页
        │   ├── NotFound.js    # 404页面
        │   ├── Search.js      # 搜索页面
        │   └── Upload.js      # 上传页面
        ├── services/          # API服务
        │   └── api.js         # API接口
        ├── utils/             # 工具函数
        └── styles/            # 样式文件
``` 