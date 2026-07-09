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

### 推荐方式：GitHub 拉代码 + Docker 部署

这是当前推荐的产线路径。不要在服务器继续使用 `./start.sh dev`。

#### 首次安装

```bash
git clone https://github.com/yourname/security-toolkit.git
cd security-toolkit

./deploy/install.sh
```

首次安装会做这些事：

- 生成 `.env`（如果还没有）
- 保留现有 `./data/toolkit.db`
- 自动备份数据库到 `./backups/`
- 构建 Docker 镜像并启动服务
- 运行数据库迁移脚本

#### 日常发布

```bash
cd security-toolkit

./deploy/deploy.sh
```

默认发布流程：

- `git fetch` + `git pull --ff-only`
- 备份 `./data/toolkit.db`
- `docker compose build`
- 运行 `python scripts/migrate_db.py`
- `docker compose up -d`

#### 数据库和数据目录

- 生产数据库默认路径：`./data/toolkit.db`
- 自动备份目录：`./backups/`
- Docker 部署使用宿主机 bind mount，不再使用 Docker named volume

#### 访问地址

- 前端：`http://服务器IP`
- API 文档：`http://服务器IP:8000/api/docs`

---

### 可选方式：离线镜像包部署

适合不能直接从 GitHub 拉代码的环境。

```bash
# 本地打包
./export-image.sh

# 上传到服务器
scp deploy/sec-toolkit-deploy.tar.gz user@your-server:~/

# 服务器解压并安装
ssh user@your-server
tar -xzf sec-toolkit-deploy.tar.gz
./install.sh
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

## 📦 运维说明

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 手动备份数据库
./deploy/backup-db.sh
```

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
