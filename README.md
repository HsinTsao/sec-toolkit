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

## 🚀 快速开始

### 一键启动 (推荐)

```bash
# 克隆项目
git clone https://github.com/yourname/security-toolkit.git
cd security-toolkit

# HTTP 模式启动 (开发)
./start.sh run

# HTTPS 模式启动 (开发) 🔒 推荐
./start.sh run-ssl

# 访问
# HTTP:  http://localhost:5173 (前端) / http://localhost:8000 (后端)
# HTTPS: https://localhost:5173 (前端) / https://localhost:8000 (后端)
```

### 使用 Docker (生产环境)

```bash
# HTTP 模式
./start.sh prod

# HTTPS 模式 🔒
./start.sh prod-ssl

# 访问
# HTTP:  http://localhost (前端) / http://localhost:8000 (后端)
# HTTPS: https://localhost (前端) / https://localhost:8000 (后端)
```

### 手动启动 (开发环境)

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# HTTP 启动
uvicorn app.main:app --reload --port 8000

# HTTPS 启动 (需要先生成证书)
uvicorn app.main:app --reload --port 8000 --ssl-keyfile=../certs/server.key --ssl-certfile=../certs/server.crt
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# HTTP 启动
npm run dev

# HTTPS 启动 (设置环境变量)
VITE_HTTPS=true VITE_API_URL=https://localhost:8000 npm run dev
```

### 🔒 HTTPS 配置

项目支持 HTTPS，适用于开发测试和生产部署。

#### 生成 SSL 证书

```bash
# 自动生成自签名证书 (用于开发/测试)
./start.sh ssl

# 或手动运行脚本
./scripts/generate-ssl-cert.sh

# 证书会生成在 certs/ 目录下
```

#### 信任自签名证书 (可选)

```bash
# macOS
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/server.crt

# Ubuntu/Debian
sudo cp certs/server.crt /usr/local/share/ca-certificates/security-toolkit.crt
sudo update-ca-certificates
```

#### 生产环境建议

生产环境建议使用正式 SSL 证书：
- [Let's Encrypt](https://letsencrypt.org/) (免费)
- 购买商业证书

将证书放入 `certs/` 目录，命名为 `server.key` 和 `server.crt`。

## 📁 项目结构

```
security-toolkit/
├── backend/                 # Python 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── models/         # 数据模型
│   │   ├── modules/        # 工具模块
│   │   │   ├── encoding/   # 编码工具
│   │   │   ├── crypto/     # 加密工具
│   │   │   ├── hash_tools/ # 哈希工具
│   │   │   ├── jwt_tool/   # JWT 工具
│   │   │   ├── network/    # 网络工具
│   │   │   └── format_tools/ # 格式工具
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # React 前端
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── features/       # 功能模块
│   │   ├── hooks/          # 自定义 hooks
│   │   ├── lib/            # 工具库
│   │   └── stores/         # 状态管理
│   ├── nginx.conf          # HTTP nginx 配置
│   ├── nginx-ssl.conf      # HTTPS nginx 配置
│   ├── package.json
│   └── Dockerfile
├── scripts/                 # 脚本目录
│   └── generate-ssl-cert.sh # SSL 证书生成脚本
├── certs/                   # SSL 证书目录 (自动生成)
├── data/                    # 数据目录 (SQLite)
├── docker-compose.yml       # Docker 配置 (HTTP)
├── docker-compose.ssl.yml   # Docker 配置 (HTTPS 覆盖)
├── start.sh                 # 一键启动脚本
├── env.example              # 环境变量示例
└── README.md
```

## 🛠 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy
- **认证**: JWT
- **缓存**: 内存缓存 (cachetools)

### 前端
- **框架**: React 18 + TypeScript
- **状态管理**: Zustand + React Query
- **样式**: Tailwind CSS
- **构建**: Vite

### 部署
- **容器**: Docker + Docker Compose
- **反代**: Nginx

## ⚙️ 环境变量

```env
# 后端配置
DATABASE_URL=sqlite+aiosqlite:///./data/toolkit.db
JWT_SECRET_KEY=your-secret-key-here
DEBUG=false
CORS_ORIGINS=["http://localhost:5173","https://localhost:5173"]

# SSL/HTTPS 配置
SSL_ENABLED=false                    # 设置为 true 启用 HTTPS
SSL_KEYFILE=../certs/server.key      # SSL 私钥路径
SSL_CERTFILE=../certs/server.crt     # SSL 证书路径

# 前端配置
VITE_HTTPS=false                     # 设置为 true 启用 HTTPS
VITE_API_URL=http://localhost:8000   # HTTPS 时改为 https://localhost:8000
```

## 📊 资源占用

| 组件 | 内存占用 |
|------|----------|
| 后端 (FastAPI) | ~80-150MB |
| 前端 (Nginx) | ~5-10MB |
| SQLite | ~0MB (文件) |
| **总计** | **~100-200MB** |

1C2G VPS 完全够用！

## 🔒 安全说明

- 密码使用 bcrypt 加密存储
- JWT Token 有效期 24 小时
- 支持笔记端到端加密
- 所有敏感操作需要认证

## 📜 开源协议

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

Made with ❤️ for Security Researchers

