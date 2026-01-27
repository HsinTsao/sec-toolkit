# Security Toolkit 🔐

个人安全工具库 - 专为信息安全从业者打造的一站式工具平台。

## ✨ 功能特性

### 🔧 安全工具集
- **编码/解码**: Base64, URL, HTML, Hex, Unicode 等
- **哈希计算**: MD5, SHA1, SHA256, SHA512, SHA3 等
- **加密/解密**: AES, RSA, DES 加密解密
- **JWT 工具**: JWT 解码、编码、验证
- **密码工具**: 密码生成器、强度检测
- **格式处理**: JSON/XML 格式化、正则测试、时间戳转换
- **网络工具**: DNS 查询、WHOIS 查询、IP 地理位置

### 📝 笔记系统
- Markdown 编辑器
- 分类和标签管理
- 全文搜索
- 笔记加密

### 🔗 资源导航
- 漏洞平台链接
- 安全社区
- 在线工具
- 靶场环境

---

## 🚀 服务器部署

### 方式一：镜像打包部署 (推荐) ⭐

**完全离线部署，不依赖任何第三方服务！**

#### 本地打包

```bash
# 在本地开发机上运行
./export-image.sh

# 输出: deploy/sec-toolkit-deploy.tar.gz
```

#### 上传到服务器

```bash
scp deploy/sec-toolkit-deploy.tar.gz user@your-server:~/
```

#### 服务器安装

```bash
# SSH 登录服务器
ssh user@your-server

# 解压部署包
tar -xzf sec-toolkit-deploy.tar.gz

# 运行安装脚本
./install.sh
```

#### 访问地址
- 前端: `http://服务器IP`
- API 文档: `http://服务器IP:8000/api/docs`

---

### 方式二：脚本部署 (需下载代码)

```bash
# 1. 克隆项目到服务器
git clone https://github.com/yourname/security-toolkit.git
cd security-toolkit

# 2. 一键部署
./start.sh prod        # HTTP 模式
./start.sh prod-ssl    # HTTPS 模式 🔒

# 访问
# HTTP:  http://服务器IP
# HTTPS: https://服务器IP
```

---

## 💻 本地开发

### 一键启动 (推荐)

```bash
# 克隆项目
git clone https://github.com/yourname/security-toolkit.git
cd security-toolkit

# HTTP 模式
./start.sh run

# HTTPS 模式 🔒 推荐
./start.sh run-ssl

# 访问
# HTTP:  http://localhost:5173
# HTTPS: https://localhost:5173
```

### 手动启动

#### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

---

## 🔒 HTTPS 配置

```bash
# 生成自签名证书 (开发/测试)
./start.sh ssl

# 证书生成在 certs/ 目录
```

生产环境建议使用 [Let's Encrypt](https://letsencrypt.org/) 证书。

---

## 📁 项目结构

```
security-toolkit/
├── backend/                 # Python 后端 (FastAPI)
├── frontend/                # React 前端 (Vite + TypeScript)
├── deploy/                  # 部署文件
│   ├── docker-compose.prod.yml
│   └── install.sh
├── scripts/                 # 脚本
├── docker-compose.yml       # Docker 配置
├── start.sh                 # 一键启动脚本
├── export-image.sh          # 镜像打包脚本
└── README.md
```

## 🛠 技术栈

| 后端 | 前端 | 部署 |
|------|------|------|
| FastAPI | React 18 | Docker |
| SQLite | TypeScript | Nginx |
| JWT | Tailwind CSS | |

## 📊 资源占用

| 组件 | 内存 |
|------|------|
| 后端 | ~80-150MB |
| 前端 | ~5-10MB |
| **总计** | **~100-200MB** |

1C2G VPS 完全够用！

---

## 📜 开源协议

MIT License

---

Made with ❤️ for Security Researchers
