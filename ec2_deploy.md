# CregisRAG EC2 部署指南

本文档提供了在Amazon EC2实例上部署CregisRAG应用的详细步骤。

## 准备工作

在开始部署之前，请确保您已经：

1. 创建了一个Amazon EC2实例（推荐t2.medium或更高配置）
2. 配置了安全组，开放以下端口：
   - SSH (22)
   - HTTP (80)
   - HTTPS (443)（如果计划使用SSL）
3. 创建了密钥对并下载了私钥文件（.pem）
4. 记录了实例的公共IP地址

## 部署步骤

### 1. 连接到EC2实例

使用SSH连接到您的EC2实例。根据您的操作系统，连接方式略有不同：

**对于Linux/macOS用户：**
```bash
chmod 400 your-key.pem
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

**对于Windows用户：**
使用PuTTY或Windows Subsystem for Linux (WSL)进行连接。如果使用PuTTY，需要先将.pem文件转换为.ppk格式。

### 2. 上传部署脚本

有两种方式可以上传部署脚本：

**方法1：直接创建脚本**
登录EC2实例后，创建脚本文件：
```bash
nano ec2_setup.sh
```

将本地的`ec2_setup.sh`脚本内容复制到编辑器中，然后按`Ctrl+O`保存，`Ctrl+X`退出。

**方法2：使用SCP上传**
在本地终端（不是EC2连接）中运行：
```bash
scp -i your-key.pem ec2_setup.sh ec2-user@your-ec2-public-ip:~/
```

### 3. 执行部署脚本

在EC2实例上，为脚本添加执行权限并运行：
```bash
chmod +x ec2_setup.sh
./ec2_setup.sh
```

脚本将执行以下操作：
- 检测Linux发行版并安装相应的软件包
- 更新系统和安装必要的依赖
- 创建项目目录结构
- 设置Python虚拟环境并安装依赖
- 创建示例应用文件
- 配置系统服务
- 配置Nginx作为反向代理
- 启动所有服务

脚本执行过程中将显示详细的日志信息，如果遇到错误，会有明确的提示。

### 4. 验证部署

部署完成后，您可以通过以下方式验证部署是否成功：

1. 在浏览器中访问 `http://your-ec2-public-ip`
2. 检查API健康状态： `http://your-ec2-public-ip/api/health`
3. 在EC2实例上检查服务状态：
   ```bash
   sudo systemctl status cregisrag
   sudo systemctl status nginx
   ```

### 5. 部署完整的CregisRAG应用

示例应用只是一个基本框架，要部署完整的CregisRAG应用，您需要：

1. 将实际的CregisRAG代码复制到EC2实例
   ```bash
   # 在您的本地机器上
   scp -i your-key.pem -r /path/to/your/CregisRAG/* ec2-user@your-ec2-public-ip:~/apps/CregisRAG/
   ```

2. 构建前端应用
   ```bash
   cd ~/apps/CregisRAG/frontend
   npm install
   npm run build
   ```

3. 重启服务
   ```bash
   sudo systemctl restart cregisrag
   sudo systemctl restart nginx
   ```

## 故障排除

如果在部署过程中遇到问题，请检查以下日志文件：

1. CregisRAG服务日志
   ```bash
   journalctl -u cregisrag
   ```

2. Nginx日志
   ```bash
   sudo tail -f /var/log/nginx/error.log
   sudo tail -f /var/log/nginx/access.log
   ```

3. 应用程序日志（如果已配置）
   ```bash
   tail -f ~/apps/CregisRAG/logs/*.log
   ```

## 安全建议

为了增强部署的安全性，建议：

1. 配置防火墙，只开放必要的端口
2. 设置SSL/TLS加密（使用Let's Encrypt等服务）
3. 定期更新系统和依赖包
4. 配置应用的身份验证机制
5. 设置数据备份策略

## 后续步骤

成功部署后，您可能需要：

1. 配置域名并设置DNS解析
2. 设置监控和告警系统
3. 配置自动备份
4. 优化性能和资源使用

---

如有任何问题或需要进一步的帮助，请参考项目文档或联系开发团队。 