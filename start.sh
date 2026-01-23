#!/bin/bash

# Security Toolkit 启动脚本
# 用法: ./start.sh [dev|prod|stop|logs|clean|ssl]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# SSL 证书路径
CERT_DIR="$PROJECT_DIR/certs"
SSL_KEY="$CERT_DIR/server.key"
SSL_CERT="$CERT_DIR/server.crt"

# 打印带颜色的消息
print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 显示 Banner
show_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║       🔐 Security Toolkit                 ║"
    echo "║       安全工具库启动脚本                   ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    print_success "依赖检查通过"
}

# 创建必要目录
setup_directories() {
    print_info "创建数据目录..."
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/certs"
    print_success "目录创建完成"
}

# 生成 SSL 证书
generate_ssl_cert() {
    if [ ! -f "$SSL_KEY" ] || [ ! -f "$SSL_CERT" ]; then
        print_info "生成 SSL 证书..."
        if [ -f "$PROJECT_DIR/scripts/generate-ssl-cert.sh" ]; then
            chmod +x "$PROJECT_DIR/scripts/generate-ssl-cert.sh"
            "$PROJECT_DIR/scripts/generate-ssl-cert.sh" "$CERT_DIR" "localhost" "365"
        else
            print_error "SSL 证书生成脚本不存在"
            exit 1
        fi
    else
        print_info "SSL 证书已存在"
    fi
}

# 生成环境变量
setup_env() {
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_info "生成环境变量文件..."
        
        # 生成随机 JWT 密钥
        JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
        
        cat > "$PROJECT_DIR/.env" << EOF
# Security Toolkit 环境变量
DATABASE_URL=sqlite+aiosqlite:///./data/toolkit.db
JWT_SECRET_KEY=${JWT_SECRET}
DEBUG=false
CORS_ORIGINS=["http://localhost","http://localhost:5173","https://localhost","https://localhost:5173"]

# SSL 配置 (设置为 true 启用 HTTPS)
SSL_ENABLED=false
SSL_KEYFILE=../certs/server.key
SSL_CERTFILE=../certs/server.crt

# 前端 HTTPS (Vite)
VITE_HTTPS=false
VITE_API_URL=http://localhost:8000
EOF
        
        print_success "环境变量文件已生成"
    else
        print_info "环境变量文件已存在，跳过"
    fi
}

# 设置 HTTPS 环境变量
setup_https_env() {
    print_info "配置 HTTPS 环境..."
    
    # 更新或创建 .env 文件中的 SSL 配置
    if [ -f "$PROJECT_DIR/.env" ]; then
        # 使用 sed 更新现有配置
        if grep -q "SSL_ENABLED" "$PROJECT_DIR/.env"; then
            sed -i.bak 's/SSL_ENABLED=.*/SSL_ENABLED=true/' "$PROJECT_DIR/.env"
        else
            echo "SSL_ENABLED=true" >> "$PROJECT_DIR/.env"
        fi
        
        if grep -q "VITE_HTTPS" "$PROJECT_DIR/.env"; then
            sed -i.bak 's/VITE_HTTPS=.*/VITE_HTTPS=true/' "$PROJECT_DIR/.env"
        else
            echo "VITE_HTTPS=true" >> "$PROJECT_DIR/.env"
        fi
        
        if grep -q "VITE_API_URL" "$PROJECT_DIR/.env"; then
            sed -i.bak 's|VITE_API_URL=.*|VITE_API_URL=https://localhost:8000|' "$PROJECT_DIR/.env"
        else
            echo "VITE_API_URL=https://localhost:8000" >> "$PROJECT_DIR/.env"
        fi
        
        rm -f "$PROJECT_DIR/.env.bak"
    fi
    
    # 导出环境变量
    export SSL_ENABLED=true
    export SSL_KEYFILE="$SSL_KEY"
    export SSL_CERTFILE="$SSL_CERT"
    export VITE_HTTPS=true
    export VITE_API_URL=https://localhost:8000
    
    print_success "HTTPS 环境配置完成"
}

# 检查服务是否已运行
is_running() {
    local service=$1
    if [ "$service" = "backend" ]; then
        pgrep -f "uvicorn app.main:app" > /dev/null 2>&1
    elif [ "$service" = "frontend" ]; then
        pgrep -f "vite" > /dev/null 2>&1
    elif [ "$service" = "docker" ]; then
        docker ps --filter "name=toolkit" --format "{{.Names}}" 2>/dev/null | grep -q "toolkit"
    fi
}

# 显示运行状态
show_status() {
    echo ""
    echo "服务状态:"
    if is_running "backend"; then
        echo -e "  ${GREEN}●${NC} 后端: 运行中"
    else
        echo -e "  ${RED}○${NC} 后端: 未运行"
    fi
    
    if is_running "frontend"; then
        echo -e "  ${GREEN}●${NC} 前端: 运行中"
    else
        echo -e "  ${RED}○${NC} 前端: 未运行"
    fi
    
    if is_running "docker"; then
        echo -e "  ${GREEN}●${NC} Docker: 运行中"
    fi
    echo ""
}

# 开发模式启动 (HTTP)
start_dev() {
    start_dev_internal false
}

# 开发模式启动 (HTTPS)
start_dev_https() {
    generate_ssl_cert
    setup_https_env
    start_dev_internal true
}

# 内部开发启动函数
start_dev_internal() {
    local use_https=$1
    local protocol="http"
    local uvicorn_ssl_args=""
    
    if [ "$use_https" = "true" ]; then
        protocol="https"
        uvicorn_ssl_args="--ssl-keyfile=$SSL_KEY --ssl-certfile=$SSL_CERT"
        print_info "启动开发环境 (HTTPS 模式)..."
    else
        print_info "启动开发环境 (HTTP 模式)..."
    fi
    
    # 检查是否已在运行
    if is_running "backend" || is_running "frontend"; then
        print_warning "服务已在运行中"
        show_status
        echo -n "是否重启服务？[y/N] "
        read -r confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            stop_services
            sleep 1
        else
            print_info "保持当前服务运行"
            echo -e "  ${GREEN}前端地址:${NC} ${protocol}://localhost:5173"
            echo -e "  ${GREEN}后端地址:${NC} ${protocol}://localhost:8000"
            return
        fi
    fi
    
    # 检查 Python 和 Node
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "Node.js/npm 未安装"
        exit 1
    fi
    
    # 后端
    print_info "启动后端服务..."
    cd "$PROJECT_DIR/backend"
    
    if [ ! -d "venv" ]; then
        print_info "创建 Python 虚拟环境..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # 安装 Python 依赖
    print_info "安装 Python 依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        print_error "Python 依赖安装失败"
        exit 1
    fi
    print_success "Python 依赖安装完成"
    
    # 后台启动后端
    print_info "启动 FastAPI 服务..."
    if [ "$use_https" = "true" ]; then
        nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 $uvicorn_ssl_args > ../data/backend.log 2>&1 &
    else
        nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../data/backend.log 2>&1 &
    fi
    echo $! > ../data/backend.pid
    sleep 2
    
    if is_running "backend"; then
        print_success "后端已启动 (PID: $(cat ../data/backend.pid))"
    else
        print_error "后端启动失败，查看日志: cat data/backend.log"
        exit 1
    fi
    
    # 前端
    print_info "启动前端服务..."
    cd "$PROJECT_DIR/frontend"
    
    if [ ! -d "node_modules" ]; then
        print_info "安装前端依赖 (npm install)..."
        npm install
        
        if [ $? -ne 0 ]; then
            print_error "前端依赖安装失败"
            exit 1
        fi
        print_success "前端依赖安装完成"
    fi
    
    # 后台启动前端
    print_info "启动 Vite 开发服务器..."
    if [ "$use_https" = "true" ]; then
        VITE_HTTPS=true VITE_API_URL="https://localhost:8000" nohup npm run dev > ../data/frontend.log 2>&1 &
    else
        nohup npm run dev > ../data/frontend.log 2>&1 &
    fi
    echo $! > ../data/frontend.pid
    sleep 2
    
    if is_running "frontend"; then
        print_success "前端已启动 (PID: $(cat ../data/frontend.pid))"
    else
        print_error "前端启动失败，查看日志: cat data/frontend.log"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    echo ""
    print_success "开发环境启动完成！"
    echo ""
    if [ "$use_https" = "true" ]; then
        echo -e "  ${GREEN}🔒 HTTPS 模式已启用${NC}"
    fi
    echo -e "  ${GREEN}前端地址:${NC} ${protocol}://localhost:5173"
    echo -e "  ${GREEN}后端地址:${NC} ${protocol}://localhost:8000"
    echo -e "  ${GREEN}API 文档:${NC} ${protocol}://localhost:8000/api/docs"
    echo ""
    echo -e "  ${YELLOW}查看日志:${NC} ./start.sh logs"
    echo -e "  ${YELLOW}停止服务:${NC} ./start.sh stop"
}

# 开发模式 - 前台运行 (实时显示后端日志)
start_dev_foreground() {
    start_dev_foreground_internal false
}

# 开发模式 - 前台运行 HTTPS
start_dev_foreground_https() {
    generate_ssl_cert
    setup_https_env
    start_dev_foreground_internal true
}

# 内部前台运行函数
start_dev_foreground_internal() {
    local use_https=$1
    local protocol="http"
    local uvicorn_ssl_args=""
    
    if [ "$use_https" = "true" ]; then
        protocol="https"
        uvicorn_ssl_args="--ssl-keyfile=$SSL_KEY --ssl-certfile=$SSL_CERT"
        print_info "启动开发环境 (前台模式，HTTPS)..."
    else
        print_info "启动开发环境 (前台模式，HTTP)..."
    fi
    
    # 先停止已有服务
    if is_running "backend" || is_running "frontend"; then
        print_warning "停止已有服务..."
        stop_services
        sleep 1
    fi
    
    # 检查依赖
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "Node.js/npm 未安装"
        exit 1
    fi
    
    # 前端 (后台启动)
    print_info "启动前端服务 (后台)..."
    cd "$PROJECT_DIR/frontend"
    
    if [ ! -d "node_modules" ]; then
        print_info "安装前端依赖..."
        npm install
    fi
    
    if [ "$use_https" = "true" ]; then
        VITE_HTTPS=true VITE_API_URL="https://localhost:8000" nohup npm run dev > ../data/frontend.log 2>&1 &
    else
        nohup npm run dev > ../data/frontend.log 2>&1 &
    fi
    echo $! > ../data/frontend.pid
    print_success "前端已启动: ${protocol}://localhost:5173"
    
    # 后端 (前台运行，实时显示日志)
    print_info "启动后端服务 (前台模式)..."
    cd "$PROJECT_DIR/backend"
    
    if [ ! -d "venv" ]; then
        print_info "创建 Python 虚拟环境..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # 安装依赖
    print_info "检查 Python 依赖..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  后端日志实时输出 (按 Ctrl+C 停止)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    if [ "$use_https" = "true" ]; then
        echo -e "  ${GREEN}🔒 HTTPS 模式已启用${NC}"
    fi
    echo -e "  ${GREEN}前端地址:${NC} ${protocol}://localhost:5173"
    echo -e "  ${GREEN}后端地址:${NC} ${protocol}://localhost:8000"
    echo -e "  ${GREEN}API 文档:${NC} ${protocol}://localhost:8000/api/docs"
    echo ""
    
    # 前台运行后端，Ctrl+C 会停止
    trap "echo ''; print_info '停止服务...'; stop_services; exit 0" SIGINT SIGTERM
    
    if [ "$use_https" = "true" ]; then
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 $uvicorn_ssl_args
    else
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    fi
}

# 生产模式启动 (Docker)
start_prod() {
    print_info "启动生产环境 (Docker)..."
    
    check_dependencies
    setup_directories
    setup_env
    
    # 使用 docker compose (新版) 或 docker-compose (旧版)
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    print_info "构建并启动容器..."
    $COMPOSE_CMD up -d --build
    
    echo ""
    print_success "生产环境启动完成！"
    echo ""
    echo -e "  ${GREEN}前端地址:${NC} http://localhost"
    echo -e "  ${GREEN}后端地址:${NC} http://localhost:8000"
    echo -e "  ${GREEN}API 文档:${NC} http://localhost:8000/api/docs"
    echo ""
    echo -e "  ${YELLOW}查看日志:${NC} ./start.sh logs"
    echo -e "  ${YELLOW}停止服务:${NC} ./start.sh stop"
}

# 生产模式启动 HTTPS (Docker)
start_prod_https() {
    print_info "启动生产环境 (Docker + HTTPS)..."
    
    check_dependencies
    setup_directories
    generate_ssl_cert
    setup_env
    
    # 使用 docker compose (新版) 或 docker-compose (旧版)
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    print_info "构建并启动容器 (HTTPS 模式)..."
    $COMPOSE_CMD -f docker-compose.yml -f docker-compose.ssl.yml up -d --build
    
    echo ""
    print_success "生产环境启动完成！"
    echo ""
    echo -e "  ${GREEN}🔒 HTTPS 模式已启用${NC}"
    echo -e "  ${GREEN}前端地址:${NC} https://localhost"
    echo -e "  ${GREEN}后端地址:${NC} https://localhost:8000"
    echo -e "  ${GREEN}API 文档:${NC} https://localhost:8000/api/docs"
    echo ""
    echo -e "  ${YELLOW}查看日志:${NC} ./start.sh logs"
    echo -e "  ${YELLOW}停止服务:${NC} ./start.sh stop"
}

# 停止服务
stop_services() {
    print_info "停止服务..."
    
    # 停止开发环境进程 (通过 PID 文件)
    if [ -f "$PROJECT_DIR/data/backend.pid" ]; then
        kill $(cat "$PROJECT_DIR/data/backend.pid") 2>/dev/null || true
        rm "$PROJECT_DIR/data/backend.pid"
        print_info "后端进程已停止"
    fi
    
    if [ -f "$PROJECT_DIR/data/frontend.pid" ]; then
        kill $(cat "$PROJECT_DIR/data/frontend.pid") 2>/dev/null || true
        rm "$PROJECT_DIR/data/frontend.pid"
        print_info "前端进程已停止"
    fi
    
    # 备用: 按进程名停止
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "vite.*security-toolkit" 2>/dev/null || true
    
    # 停止 Docker 容器 (如果有)
    if command -v docker &> /dev/null; then
        if docker compose version &> /dev/null; then
            docker compose down 2>/dev/null || true
        else
            docker-compose down 2>/dev/null || true
        fi
    fi
    
    print_success "所有服务已停止"
}

# 查看日志
show_logs() {
    echo "选择要查看的日志:"
    echo "  1) 后端日志 (开发)"
    echo "  2) 前端日志 (开发)"
    echo "  3) Docker 日志 (生产)"
    echo ""
    read -p "请输入选项 [1-3]: " choice
    
    case $choice in
        1)
            if [ -f "$PROJECT_DIR/data/backend.log" ]; then
                tail -f "$PROJECT_DIR/data/backend.log"
            else
                print_warning "后端日志文件不存在"
            fi
            ;;
        2)
            if [ -f "$PROJECT_DIR/data/frontend.log" ]; then
                tail -f "$PROJECT_DIR/data/frontend.log"
            else
                print_warning "前端日志文件不存在"
            fi
            ;;
        3)
            if docker compose version &> /dev/null; then
                docker compose logs -f
            else
                docker-compose logs -f
            fi
            ;;
        *)
            print_error "无效选项"
            ;;
    esac
}

# 生成 SSL 证书命令
ssl_cert_cmd() {
    setup_directories
    generate_ssl_cert
}

# 清理
clean() {
    print_warning "这将删除所有容器、镜像和数据，确定继续？[y/N]"
    read -p "" confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        stop_services
        
        print_info "清理 Docker 资源..."
        if docker compose version &> /dev/null; then
            docker compose down -v --rmi all 2>/dev/null || true
        else
            docker-compose down -v --rmi all 2>/dev/null || true
        fi
        
        print_info "清理数据目录..."
        rm -rf "$PROJECT_DIR/data"/*.db
        rm -rf "$PROJECT_DIR/data"/*.log
        rm -rf "$PROJECT_DIR/data"/*.pid
        
        print_info "清理前端依赖..."
        rm -rf "$PROJECT_DIR/frontend/node_modules"
        rm -rf "$PROJECT_DIR/frontend/dist"
        
        print_info "清理后端虚拟环境..."
        rm -rf "$PROJECT_DIR/backend/venv"
        rm -rf "$PROJECT_DIR/backend/__pycache__"
        
        print_success "清理完成"
    else
        print_info "已取消"
    fi
}

# 显示帮助
show_help() {
    echo "用法: ./start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  dev       启动开发环境 - HTTP (后台运行)"
    echo "  dev-ssl   启动开发环境 - HTTPS (后台运行) 🔒"
    echo "  run       启动开发环境 - HTTP (前台运行，实时日志)"
    echo "  run-ssl   启动开发环境 - HTTPS (前台运行，实时日志) 🔒 ⭐"
    echo "  prod      启动生产环境 - HTTP (Docker)"
    echo "  prod-ssl  启动生产环境 - HTTPS (Docker) 🔒"
    echo "  stop      停止所有服务"
    echo "  status    查看服务状态"
    echo "  logs      查看日志"
    echo "  ssl       生成 SSL 证书"
    echo "  clean     清理所有数据和依赖"
    echo "  help      显示帮助信息"
    echo ""
    echo "示例:"
    echo "  ./start.sh run-ssl  # 开发模式 HTTPS (前台) 推荐"
    echo "  ./start.sh dev-ssl  # 开发模式 HTTPS (后台)"
    echo "  ./start.sh run      # 开发模式 HTTP (前台)"
    echo "  ./start.sh ssl      # 仅生成 SSL 证书"
    echo ""
    echo "数据持久化:"
    echo "  - 数据库:     data/toolkit.db"
    echo "  - SSL 证书:   certs/"
    echo "  - Python 环境: backend/venv/"
    echo "  - Node 依赖:   frontend/node_modules/"
}

# 主函数
main() {
    show_banner
    
    case "${1:-}" in
        dev)
            setup_directories
            setup_env
            start_dev
            ;;
        dev-ssl)
            setup_directories
            setup_env
            start_dev_https
            ;;
        run)
            setup_directories
            setup_env
            start_dev_foreground
            ;;
        run-ssl)
            setup_directories
            setup_env
            start_dev_foreground_https
            ;;
        prod)
            start_prod
            ;;
        prod-ssl)
            start_prod_https
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        ssl)
            ssl_cert_cmd
            ;;
        clean)
            clean
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            echo "请选择启动模式:"
            echo "  1) 开发模式 - HTTPS 前台运行 (run-ssl) 🔒 ⭐ 推荐"
            echo "  2) 开发模式 - HTTP 前台运行 (run)"
            echo "  3) 开发模式 - HTTPS 后台运行 (dev-ssl) 🔒"
            echo "  4) 开发模式 - HTTP 后台运行 (dev)"
            echo "  5) 生产模式 - HTTPS (prod-ssl) 🔒"
            echo "  6) 生产模式 - HTTP (prod)"
            echo ""
            read -p "请输入选项 [1-6]: " mode
            
            case $mode in
                1) setup_directories; setup_env; start_dev_foreground_https ;;
                2) setup_directories; setup_env; start_dev_foreground ;;
                3) setup_directories; setup_env; start_dev_https ;;
                4) setup_directories; setup_env; start_dev ;;
                5) start_prod_https ;;
                6) start_prod ;;
                *) print_error "无效选项" ;;
            esac
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
