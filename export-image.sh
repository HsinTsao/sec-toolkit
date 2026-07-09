#!/bin/bash

# Security Toolkit 镜像打包脚本
# 构建并导出 Docker 镜像，用于服务器离线部署
#
# 用法: ./export-image.sh
# 输出: deploy/sec-toolkit-deploy.tar.gz (包含镜像和部署脚本)

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 输出目录
OUTPUT_DIR="$PROJECT_DIR/deploy"
IMAGES_FILE="$OUTPUT_DIR/sec-toolkit-images.tar"
DEPLOY_PACKAGE="$OUTPUT_DIR/sec-toolkit-deploy.tar.gz"

# 镜像名
BACKEND_IMAGE="sec-toolkit-backend:latest"
FRONTEND_IMAGE="sec-toolkit-frontend:latest"

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     🔐 Security Toolkit 镜像打包          ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker 未安装"
    exit 1
fi

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

# 目标平台 (服务器通常是 x86_64)
PLATFORM="linux/amd64"

# 构建后端镜像
print_info "构建后端镜像 (平台: ${PLATFORM})..."
docker build --platform "${PLATFORM}" -t "${BACKEND_IMAGE}" ./backend
if [ $? -eq 0 ]; then
    print_success "后端镜像构建完成"
else
    print_error "后端镜像构建失败"
    exit 1
fi

# 构建前端镜像
print_info "构建前端镜像 (平台: ${PLATFORM})..."
docker build --platform "${PLATFORM}" -t "${FRONTEND_IMAGE}" ./frontend
if [ $? -eq 0 ]; then
    print_success "前端镜像构建完成"
else
    print_error "前端镜像构建失败"
    exit 1
fi

# 导出镜像
print_info "导出镜像..."
docker save ${BACKEND_IMAGE} ${FRONTEND_IMAGE} -o "${IMAGES_FILE}"
print_success "镜像导出完成"

# 打包部署文件
print_info "打包部署文件..."
cd "$OUTPUT_DIR"
tar -czf sec-toolkit-deploy.tar.gz \
    sec-toolkit-images.tar \
    docker-compose.prod.yml \
    docker-compose.prod-ssl.yml \
    install.sh \
    backup-db.sh \
    preflight.sh \
    nginx-ssl.conf

# 清理临时文件
rm -f sec-toolkit-images.tar

# 显示结果
FILE_SIZE=$(ls -lh "$DEPLOY_PACKAGE" | awk '{print $5}')

echo ""
print_success "打包完成！"
echo ""
echo -e "  ${GREEN}部署包:${NC} deploy/sec-toolkit-deploy.tar.gz"
echo -e "  ${GREEN}大小:${NC}   ${FILE_SIZE}"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  服务器部署步骤:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""
echo "  1. 上传部署包到服务器:"
echo -e "     ${CYAN}scp deploy/sec-toolkit-deploy.tar.gz user@server:~/${NC}"
echo ""
echo "  2. SSH 登录服务器并解压:"
echo -e "     ${CYAN}tar -xzf sec-toolkit-deploy.tar.gz${NC}"
echo ""
echo "  3. 运行安装脚本:"
echo -e "     ${CYAN}./install.sh${NC}"
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  配置管理:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""
echo "  所有配置集中在 .env 文件中，修改后重启即可生效:"
echo -e "     ${CYAN}nano .env                                              # 编辑配置${NC}"
echo -e "     ${CYAN}./backup-db.sh                                         # 手动备份数据库${NC}"
echo -e "     ${CYAN}docker compose -f docker-compose.prod.yml up -d       # 重启生效${NC}"
echo ""
echo "  无需重新打包镜像，后端新增的配置项直接在 .env 中添加即可"
echo ""
