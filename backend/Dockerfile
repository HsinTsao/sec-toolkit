# Python 后端 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# 安装系统依赖
# - gcc: 编译 Python 扩展
# - curl: 健康检查
# - libffi-dev: cffi 依赖
# - Playwright 依赖: libnss3, libatk1.0-0, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    libffi-dev \
    # Playwright Chromium 依赖
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器（仅 Chromium）
RUN playwright install chromium --with-deps || echo "Playwright install skipped"

# 复制应用代码
COPY . .

# 创建数据目录并设置权限
RUN mkdir -p /app/data && chmod 755 /app/data

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令（生产环境建议使用 gunicorn）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

