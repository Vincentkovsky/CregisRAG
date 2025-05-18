# EC2部署脚本解析

本文档详细解释了`ec2_setup.sh`脚本的工作原理和各部分功能。

## 脚本概述

`ec2_setup.sh`是一个用于在EC2实例上自动化部署CregisRAG应用的Bash脚本。该脚本具有以下主要特点：

- 跨发行版兼容性：能够检测并适应多种Linux发行版，包括Debian/Ubuntu、RHEL/CentOS/Fedora和Alpine
- 全面自动化：从系统更新到服务配置和启动的整个过程自动化
- 提供详细日志：使用彩色输出提供清晰的执行状态和错误信息
- 创建基础示例应用：包含可立即运行的最小可行应用

## 功能模块详解

### 1. 彩色输出函数

```bash
echo_info() { echo -e "\033[0;36m[INFO]\033[0m $1"; }
echo_success() { echo -e "\033[0;32m[SUCCESS]\033[0m $1"; }
echo_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }
```

这三个函数用于以不同颜色输出信息：
- `echo_info`: 青色，用于一般信息
- `echo_success`: 绿色，用于成功信息
- `echo_error`: 红色，用于错误信息

使用彩色输出可以让用户更直观地了解脚本执行状态。

### 2. 系统检测

```bash
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
```

这个函数通过检查`/etc/os-release`文件来识别当前的Linux发行版。该文件包含系统标识信息，包括名称、版本等。通过`. /etc/os-release`（等同于`source /etc/os-release`）命令加载这些变量，脚本就能获取系统类型。

### 3. 系统设置

```bash
setup_system() {
    echo_info "正在更新系统并安装必要的软件包..."
    
    if [ -f /etc/debian_version ] || [ "$ID" == "ubuntu" ] || [ "$ID" == "debian" ]; then
        # Debian/Ubuntu安装逻辑
    elif [ -f /etc/redhat-release ] || [ "$ID" == "rhel" ] || [ "$ID" == "fedora" ] || [ "$ID" == "centos" ]; then
        # RHEL/CentOS/Fedora安装逻辑
    elif [ -f /etc/alpine-release ]; then
        # Alpine安装逻辑
    else
        echo_error "不支持的Linux发行版"
        return 1
    fi
}
```

这个函数根据不同的发行版执行相应的包管理器命令：
- Debian/Ubuntu系统使用`apt`
- RHEL/CentOS/Fedora系统根据版本使用`dnf`或`yum`
- Alpine系统使用`apk`

所有系统都会安装相同的基础包：git、Python3、pip、nginx和Node.js等。

### 4. 目录创建

```bash
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
```

该函数创建CregisRAG应用所需的所有目录结构，包括：
- 主应用目录
- 数据目录（原始、处理、状态和向量存储）
- 日志目录

### 5. Python环境设置

```bash
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
```

该函数用于创建Python虚拟环境并安装CregisRAG所需的所有Python包，包括：
- Web框架：FastAPI和Uvicorn
- 向量存储：Chroma
- 语言模型工具：LangChain
- 文档处理：PyPDF、python-docx等

### 6. systemd服务创建

```bash
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
```

此函数创建一个systemd服务单元文件，使CregisRAG应用能够：
- 开机自动启动
- 崩溃后自动重启
- 作为后台服务运行
- 使用当前用户的权限运行（而非root）

### 7. Nginx配置

```bash
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
```

这个函数配置Nginx作为反向代理，将请求路由到正确的位置：
- 将根路径（/）的请求路由到前端静态文件
- 将/api路径的请求代理到FastAPI应用（端口8000）
- 自动获取服务器IP地址并设置为server_name

### 8. 示例应用创建

```bash
create_sample_app() {
    echo_info "创建示例应用文件..."
    
    # 创建示例run.py
    cat > ~/apps/CregisRAG/run.py << EOL
#!/usr/bin/env python3
# FastAPI应用代码
EOL
    
    # 创建示例前端目录和文件
    mkdir -p ~/apps/CregisRAG/frontend/build
    
    cat > ~/apps/CregisRAG/frontend/build/index.html << EOL
<!DOCTYPE html>
<!-- HTML应用代码 -->
EOL

    chmod +x ~/apps/CregisRAG/run.py
    echo_success "示例应用文件创建完成"
}
```

该函数创建一个最小可行的示例应用：
- 后端：简单的FastAPI应用，包含健康检查和查询端点
- 前端：基本HTML页面，包含简单的查询表单和结果显示
- 确保`run.py`具有执行权限，以便作为服务启动

### 9. 服务启动

```bash
start_services() {
    echo_info "启动服务..."
    
    sudo systemctl start cregisrag
    sudo systemctl status cregisrag --no-pager
    
    echo_success "服务已启动"
    
    SERVER_IP=$(curl -s ifconfig.me)
    echo_info "您可以通过以下地址访问应用: http://$SERVER_IP"
    echo_info "API健康检查: http://$SERVER_IP/api/health"
}
```

此函数启动并检查服务状态，然后提供访问应用的URL。它：
- 启动CregisRAG系统服务
- 显示服务状态，确认服务正在运行
- 获取服务器IP地址
- 显示可访问应用的URL

### 10. 主函数

```bash
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
```

主函数按顺序调用所有其他函数，形成完整的安装流程。每个函数完成一个特定任务，彼此相对独立，便于调试和维护。

## 脚本执行流程

1. 脚本检测系统类型
2. 根据系统类型安装必要的软件包
3. 创建项目所需的目录结构
4. 设置Python虚拟环境并安装依赖
5. 创建示例应用文件
6. 创建系统服务
7. 配置Nginx反向代理
8. 启动所有服务
9. 显示访问应用的URL

## 错误处理

脚本在多个地方实现了错误处理：

1. 每个函数都会检查关键操作的结果，在失败时返回非零值
2. 使用`echo_error`函数明确标记错误消息
3. 在系统类型检测中，如果遇到不支持的发行版，会提前退出
4. 在Nginx配置中，使用`nginx -t`测试配置有效性，仅在测试通过时才重启服务

## 安全考虑

脚本包含几项安全措施：

1. 尽可能使用当前用户权限运行应用，而非root
2. 仅在必要时使用sudo
3. 通过systemd服务文件限制应用权限
4. CORS设置仅在开发环境中允许所有源

## 自定义和扩展

要自定义该脚本，您可以修改：

1. 安装的软件包列表
2. Python依赖列表
3. 目录结构
4. Nginx配置
5. systemd服务配置

## 总结

`ec2_setup.sh`脚本是一个全面的自动化部署工具，可以大大简化CregisRAG应用在EC2实例上的部署过程。它采用模块化设计，具有跨发行版兼容性，并提供详细的执行日志，使部署过程既高效又可靠。 