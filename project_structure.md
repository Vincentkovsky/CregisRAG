# CregisRAG 项目结构

```
CregisRAG/
│
├── README.md                  # 项目说明文档
├── LICENSE                    # 开源许可证
├── CONTRIBUTING.md            # 贡献指南
├── .gitignore                 # Git忽略文件
├── requirements.txt           # Python依赖列表
├── pyproject.toml             # 项目构建配置
├── config.yml                 # 项目配置文件
├── run.py                     # 主启动脚本
│
├── app/                       # 应用核心代码
│   ├── __init__.py
│   ├── api/                   # API接口层
│   │   ├── __init__.py
│   │   ├── routes/            # API路由定义
│   │   │   ├── __init__.py
│   │   │   ├── query.py       # 查询接口
│   │   │   ├── ingest.py      # 数据摄入接口
│   │   │   └── admin.py       # 管理接口
│   │   ├── models/            # API数据模型
│   │   │   ├── __init__.py
│   │   │   ├── requests.py    # 请求模型
│   │   │   └── responses.py   # 响应模型
│   │   └── middleware/        # API中间件
│   │       ├── __init__.py
│   │       └── auth.py        # 认证中间件
│   │
│   ├── core/                  # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── ingest/            # 数据摄取模块
│   │   │   ├── __init__.py
│   │   │   ├── parser.py      # 文档解析器
│   │   │   ├── chunker.py     # 文本分块器
│   │   │   └── cleaner.py     # 数据清洗
│   │   │
│   │   ├── embedding/         # 向量化模块
│   │   │   ├── __init__.py
│   │   │   ├── models.py      # 嵌入模型
│   │   │   └── batch.py       # 批量处理
│   │   │
│   │   ├── retrieval/         # 检索模块
│   │   │   ├── __init__.py
│   │   │   ├── vectordb.py    # 向量数据库接口
│   │   │   ├── search.py      # 相似度搜索
│   │   │   └── ranking.py     # 结果排序
│   │   │
│   │   ├── generation/        # 生成模块
│   │   │   ├── __init__.py
│   │   │   ├── llm.py         # LLM接口
│   │   │   ├── prompt.py      # 提示工程
│   │   │   └── synthesis.py   # 结果合成
│   │   │
│   │   └── feedback/          # 反馈处理模块
│   │       ├── __init__.py
│   │       ├── collector.py   # 反馈收集
│   │       └── learner.py     # 增量学习
│   │
│   ├── services/              # 外部服务集成
│   │   ├── __init__.py
│   │   ├── openai.py          # OpenAI API集成
│   │   ├── claude.py          # Claude API集成
│   │   └── storage.py         # 存储服务
│   │
│   ├── utils/                 # 通用工具函数
│   │   ├── __init__.py
│   │   ├── logger.py          # 日志工具
│   │   ├── metrics.py         # 指标收集
│   │   └── helpers.py         # 辅助函数
│   │
│   └── config/                # 配置加载模块
│       ├── __init__.py
│       └── settings.py        # 设置加载
│
├── tests/                     # 测试代码
│   ├── __init__.py
│   ├── conftest.py            # 测试配置
│   ├── test_ingest.py         # 摄取测试
│   ├── test_embedding.py      # 向量化测试
│   ├── test_retrieval.py      # 检索测试
│   ├── test_generation.py     # 生成测试
│   └── test_api.py            # API测试
│
├── docs/                      # 文档
│   ├── architecture.md        # 架构文档
│   ├── api.md                 # API文档
│   ├── deployment.md          # 部署指南
│   └── development.md         # 开发指南
│
├── scripts/                   # 脚本工具
│   ├── setup.sh               # 环境设置脚本
│   ├── ingest_data.py         # 数据摄取脚本
│   └── benchmark.py           # 性能测试脚本
│
├── data/                      # 数据目录
│   ├── raw/                   # 原始数据
│   ├── processed/             # 处理后数据
│   └── embeddings/            # 嵌入向量
│
└── frontend/                  # 前端代码
    ├── package.json           # NPM配置
    ├── tsconfig.json          # TypeScript配置
    ├── public/                # 静态资源
    │   ├── index.html
    │   └── assets/
    │
    ├── src/                   # 源代码
    │   ├── index.tsx          # 入口文件
    │   ├── App.tsx            # 主应用组件
    │   ├── components/        # UI组件
    │   │   ├── SearchBar.tsx
    │   │   ├── ResultList.tsx
    │   │   ├── SourceView.tsx
    │   │   └── UploadForm.tsx
    │   │
    │   ├── pages/             # 页面组件
    │   │   ├── Home.tsx
    │   │   ├── Search.tsx
    │   │   ├── Upload.tsx
    │   │   └── Admin.tsx
    │   │
    │   ├── services/          # API服务
    │   │   ├── api.ts
    │   │   └── types.ts
    │   │
    │   ├── utils/             # 工具函数
    │   │   ├── formatting.ts
    │   │   └── validation.ts
    │   │
    │   └── styles/            # 样式文件
    │       ├── global.css
    │       └── theme.ts
    │
    └── test/                  # 前端测试
        └── components.test.tsx
``` 