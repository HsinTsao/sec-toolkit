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
- 自动做发布前快照到 `./backups/`
- 快照包含数据库、上传文件和日志归档
- 构建 Docker 镜像并启动服务
- 运行数据库迁移脚本

#### 日常发布

```bash
cd security-toolkit

./deploy/preflight.sh
./deploy/deploy.sh
```

如果服务器拉不到 Docker Hub 基础镜像，可以先在 `.env` 中覆盖基础镜像地址，再重新执行安装或发布：

```bash
PYTHON_BASE_IMAGE=python:3.11-slim
NODE_BASE_IMAGE=node:20-alpine
NGINX_BASE_IMAGE=nginx:alpine
```

把它们替换成你的服务器实际可访问的镜像地址，例如公司私有镜像仓库或镜像代理。

默认发布流程：

- `git fetch` + `git pull --ff-only`
- 自动裁剪旧快照后，备份数据库、上传文件、日志
- 自动清理 Docker build cache / dangling images
- `docker compose build`
- 运行 `python scripts/migrate_db.py`
- `docker compose up -d`

#### 数据库和数据目录

- 生产数据库默认路径：`./data/toolkit.db`
- 上传文件默认路径：`./data/uploads/`
- 文件式 Quick PoC 默认目录：`./data/poc-files/`
- 自动备份目录：`./backups/`
- 后端日志目录：`./logs/backend/`
- Nginx 访问/错误日志目录：`./logs/nginx/`
- Docker 部署使用宿主机 bind mount，不再使用 Docker named volume

空间相关默认策略：

- 自动只保留最近 `3` 份快照，可通过 `APP_BACKUP_KEEP_COUNT` 调整
- 发布预检要求至少保留 `3072MB` 空闲磁盘，可通过 `APP_MIN_FREE_SPACE_MB` 调整
- 发布前默认执行 `docker image prune -f`
- 默认不清 `docker builder prune -af`，避免每次发布都丢失构建缓存导致明显变慢

如果你的服务器在国内，Docker build 阶段的 `pip install` / `npm ci` 很慢，建议在 `.env` 中增加：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
DEPLOY_PRUNE_BUILD_CACHE=false
```

这样会同时解决两类常见慢点：

- Python / Node 依赖下载走国内镜像
- 不再每次发布都清空 Docker build cache

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

# 服务器预检
./deploy/preflight.sh

# 查看宿主机持久化日志
ls logs/backend
ls logs/nginx

# 手动做完整快照
./deploy/backup-db.sh
```

如果发布时看到 `sqlite3.OperationalError: database or disk is full`，这通常不是数据库损坏，而是服务器磁盘空间不足，最常见是以下几类空间占满：

- `backups/` 旧快照过多
- Docker 镜像 / build cache 占满磁盘
- `logs/backend/` 或 `logs/nginx/` 日志累计过大

先在服务器排查：

```bash
df -h
df -i
du -sh backups logs data /var/lib/docker 2>/dev/null
docker system df
```

常见清理方式：

```bash
# 清理旧快照（确认不需要后再删）
ls -1dt backups/snapshot-* | tail -n +6 | xargs -r rm -rf

# 清理 Docker 构建缓存和悬空镜像
docker builder prune -af
docker image prune -af
```

如果你希望把快照保留得更少，例如服务器磁盘较小，可以在 `.env` 中设置：

```bash
APP_BACKUP_KEEP_COUNT=2
APP_MIN_FREE_SPACE_MB=4096
```

如果你确实需要在发布前顺手清理 Docker build cache，可以显式开启：

```bash
DEPLOY_PRUNE_BUILD_CACHE=true
```

注意这会让后续 `docker compose build` 失去缓存，重新执行依赖安装，发布会明显变慢。

## ⚡ 文件式 Quick PoC

如果你只是想快速提供一个现成的 HTML / JS / TXT 响应，不想写 Python handler，可以直接把文件放进：

```bash
data/poc-files/
```

规则：

- `data/poc-files/test.html` -> `GET /p/test`
- `data/poc-files/payload.js` -> `GET /p/payload`
- `data/poc-files/kit/index.html` -> `GET /p/kit`
- `data/poc-files/kit/evil.js` -> `GET /p/kit/evil.js`

常见用法：

```bash
mkdir -p data/poc-files
echo '<script>alert(1)</script>' > data/poc-files/xss.html
echo 'console.log(document.domain)' > data/poc-files/probe.js
```

然后访问：

- `/p/xss`
- `/p/probe`

这类文件式 PoC 会自动出现在 Quick PoC 列表里，并且会被发布前快照一起备份。

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
