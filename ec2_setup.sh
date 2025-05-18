#!/bin/bash

# 输出带颜色的信息
echo_info() {
    echo -e "\033[0;36m[INFO]\033[0m $1"
}

echo_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

echo_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# 检测Linux发行版
detect_distro() {
    echo_info "检测Linux发行版..."
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$NAME
        echo_info "检测到系统: $DISTRO"
        return 0
    else
        echo_error "无法检测系统类型"
        return 1
    fi
}

# 更新系统和安装基础软件包
setup_system() {
    echo_info "正在更新系统并安装必要的软件包..."
    
    if [ -f /etc/debian_version ] || [ "$ID" == "ubuntu" ] || [ "$ID" == "debian" ]; then
        # Debian/Ubuntu
        sudo apt update -y
        sudo apt upgrade -y
        sudo apt install -y git python3 python3-pip python3-venv nginx curl
        
        # 安装Node.js
        if ! command -v node &> /dev/null; then
            echo_info "安装Node.js..."
            curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
    
    elif [ -f /etc/redhat-release ] || [ "$ID" == "rhel" ] || [ "$ID" == "fedora" ] || [ "$ID" == "centos" ]; then
        # RHEL/CentOS/Fedora
        if command -v dnf &> /dev/null; then
            sudo dnf update -y
            sudo dnf install -y git python3 python3-pip nginx curl
            
            # 安装Node.js
            if ! command -v node &> /dev/null; then
                echo_info "安装Node.js..."
                curl -fsSL https://rpm.nodesource.com/setup_16.x | sudo bash -
                sudo dnf install -y nodejs
            fi
        else
            sudo yum update -y
            sudo yum install -y git python3 python3-pip nginx curl
            
            # 安装Node.js
            if ! command -v node &> /dev/null; then
                echo_info "安装Node.js..."
                curl -fsSL https://rpm.nodesource.com/setup_16.x | sudo bash -
                sudo yum install -y nodejs
            fi
        fi
        
    elif [ -f /etc/alpine-release ]; then
        # Alpine
        sudo apk update
        sudo apk add git python3 py3-pip nginx nodejs npm curl
        
    else
        echo_error "不支持的Linux发行版"
        return 1
    fi
    
    echo_success "系统更新完成，基础软件包已安装"
    return 0
}

# 创建项目目录
setup_project_directories() {
    echo_info "创建项目目录..."
    
    mkdir -p ~/apps/CregisRAG
    mkdir -p ~/apps/CregisRAG/data/raw
    mkdir -p ~/apps/CregisRAG/data/processed
    mkdir -p ~/apps/CregisRAG/data/status
    mkdir -p ~/apps/CregisRAG/data/chroma
    mkdir -p ~/apps/CregisRAG/logs
    
    echo_success "项目目录创建完成"
}

# 创建Python虚拟环境
setup_python_env() {
    echo_info "设置Python虚拟环境..."
    
    cd ~/apps/CregisRAG
    python3 -m venv venv
    source venv/bin/activate
    
    pip install --upgrade pip
    
    echo_info "安装Python依赖..."
    pip install fastapi uvicorn python-multipart pydantic pyyaml
    pip install sentence-transformers chromadb langchain
    pip install pypdf python-docx markdown beautifulsoup4 requests
    
    echo_success "Python环境设置完成"
}

# 创建服务文件
create_systemd_service() {
    echo_info "创建服务文件..."
    
    sudo bash -c 'cat > /etc/systemd/system/cregisrag.service << EOL
[Unit]
Description=CregisRAG API Service
After=network.target

[Service]
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$HOME/apps/CregisRAG
Environment="PATH=$HOME/apps/CregisRAG/venv/bin"
ExecStart=$HOME/apps/CregisRAG/venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL'
    
    sudo systemctl daemon-reload
    sudo systemctl enable cregisrag
    
    echo_success "服务文件创建完成"
}

# 配置Nginx
configure_nginx() {
    echo_info "配置Nginx..."
    
    # 获取服务器IP地址
    SERVER_IP=$(curl -s ifconfig.me)
    
    sudo bash -c "cat > /etc/nginx/conf.d/cregisrag.conf << EOL
server {
    listen 80;
    server_name $SERVER_IP;

    # 前端静态文件
    location / {
        root $HOME/apps/CregisRAG/frontend/build;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # API代理
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOL"
    
    # 禁用默认配置（如果存在）
    if [ -f /etc/nginx/sites-enabled/default ]; then
        sudo rm /etc/nginx/sites-enabled/default
    fi
    
    # 重启Nginx
    if sudo nginx -t; then
        sudo systemctl enable nginx
        sudo systemctl restart nginx
        echo_success "Nginx配置完成并重启"
    else
        echo_error "Nginx配置测试失败，请检查配置"
    fi
}

# 添加示例应用文件
create_sample_app() {
    echo_info "创建示例应用文件..."
    
    # 创建示例run.py
    cat > ~/apps/CregisRAG/run.py << EOL
#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="CregisRAG API", description="检索增强生成系统")

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "CregisRAG服务运行正常"}

@app.get("/api/query")
async def query(q: str = ""):
    if not q:
        raise HTTPException(status_code=400, detail="查询参数不能为空")
    return {
        "query": q,
        "answer": f"这是对'{q}'的回答。这是一个示例响应，完整功能需要实现正确的API。",
        "sources": []
    }

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=8000)
EOL
    
    # 创建示例前端目录和文件
    mkdir -p ~/apps/CregisRAG/frontend/build
    
    cat > ~/apps/CregisRAG/frontend/build/index.html << EOL
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CregisRAG</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #333; }
        .query-form { margin-bottom: 20px; }
        input { padding: 8px; width: 70%; }
        button { padding: 8px 15px; background: #4CAF50; color: white; border: none; cursor: pointer; }
        #result { padding: 15px; background: #f5f5f5; border-radius: 5px; min-height: 100px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>CregisRAG 示例</h1>
        <div class="query-form">
            <input type="text" id="query" placeholder="输入您的问题...">
            <button onclick="sendQuery()">查询</button>
        </div>
        <div id="result">
            <p>查询结果将显示在这里...</p>
        </div>
    </div>

    <script>
        async function sendQuery() {
            const query = document.getElementById('query').value;
            if (!query) return;
            
            document.getElementById('result').innerHTML = '<p>正在处理查询...</p>';
            
            try {
                const response = await fetch(\`/api/query?q=\${encodeURIComponent(query)}\`);
                const data = await response.json();
                
                document.getElementById('result').innerHTML = \`
                    <h3>问题: \${data.query}</h3>
                    <p>\${data.answer}</p>
                \`;
            } catch (error) {
                document.getElementById('result').innerHTML = \`<p>错误: \${error.message}</p>\`;
            }
        }
    </script>
</body>
</html>
EOL

    chmod +x ~/apps/CregisRAG/run.py
    echo_success "示例应用文件创建完成"
}

# 启动服务
start_services() {
    echo_info "启动服务..."
    
    sudo systemctl start cregisrag
    sudo systemctl status cregisrag --no-pager
    
    echo_success "服务已启动"
    
    SERVER_IP=$(curl -s ifconfig.me)
    echo_info "您可以通过以下地址访问应用: http://$SERVER_IP"
    echo_info "API健康检查: http://$SERVER_IP/api/health"
}

# 执行安装流程
main() {
    echo_info "开始CregisRAG安装..."
    
    detect_distro
    setup_system
    setup_project_directories
    setup_python_env
    create_sample_app
    create_systemd_service
    configure_nginx
    start_services
    
    echo_success "CregisRAG安装完成!"
}

# 执行主函数
main 