#!/bin/bash

# Security Toolkit 服务器安装脚本
# 用法: ./install.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     🔐 Security Toolkit 安装              ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker 未安装！"
    echo ""
    echo "请先安装 Docker:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    echo "  # 重新登录后再运行此脚本"
    exit 1
fi
print_success "Docker 已安装"

# 检查 Docker Compose
if ! docker compose version &> /dev/null 2>&1; then
    print_error "Docker Compose 未安装！"
    exit 1
fi
print_success "Docker Compose 已安装"

# 检查镜像文件
if [ ! -f "sec-toolkit-images.tar" ]; then
    print_error "镜像文件 sec-toolkit-images.tar 不存在"
    exit 1
fi

# 加载镜像
print_info "加载 Docker 镜像..."
docker load -i sec-toolkit-images.tar
print_success "镜像加载完成"

# 创建 .env 文件
if [ ! -f ".env" ]; then
    print_info "生成配置文件..."
    
    # 生成随机 JWT 密钥
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '\n/+=' | head -c 64)
    
    cat > .env << EOF
# Security Toolkit 配置
# JWT 密钥 (已自动生成)
JWT_SECRET_KEY=${JWT_SECRET}

# CORS 配置 (如需添加域名，取消注释并修改)
# CORS_ORIGINS=["http://your-domain.com","https://your-domain.com"]
EOF
    
    print_success "配置文件已生成"
else
    print_info "配置文件已存在，跳过"
fi

# 启动服务
print_info "启动服务..."
docker compose -f docker-compose.prod.yml up -d

# 等待服务启动
print_info "等待服务启动..."
sleep 8

# 检查服务状态
echo ""
BACKEND_STATUS=$(docker ps --filter "name=toolkit-backend" --format "{{.Status}}" 2>/dev/null)
FRONTEND_STATUS=$(docker ps --filter "name=toolkit-frontend" --format "{{.Status}}" 2>/dev/null)

if echo "$BACKEND_STATUS" | grep -q "Up"; then
    print_success "后端服务: 运行中"
else
    print_warning "后端服务: 启动中或异常"
    echo "  查看日志: docker logs toolkit-backend"
fi

if echo "$FRONTEND_STATUS" | grep -q "Up"; then
    print_success "前端服务: 运行中"
else
    print_warning "前端服务: 启动中或异常 (可能在等待后端)"
    echo "  查看日志: docker logs toolkit-frontend"
fi

# 获取服务器 IP
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="<服务器IP>"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}访问地址:${NC}"
echo -e "    前端:    http://${SERVER_IP}"
echo -e "    API文档: http://${SERVER_IP}:8000/api/docs"
echo ""
echo -e "  ${YELLOW}常用命令:${NC}"
echo "    查看状态: docker compose -f docker-compose.prod.yml ps"
echo "    查看日志: docker compose -f docker-compose.prod.yml logs -f"
echo "    停止服务: docker compose -f docker-compose.prod.yml down"
echo "    重启服务: docker compose -f docker-compose.prod.yml restart"
echo ""
