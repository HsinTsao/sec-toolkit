#!/bin/bash

# Security Toolkit 启动脚本
# 用法: ./start.sh [命令] [--ssl]

# ==================== 配置 ====================
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
DATA_DIR="$PROJECT_DIR/data"
CERT_DIR="$PROJECT_DIR/certs"

# 端口配置
FRONTEND_PORT=80
BACKEND_PORT=8000

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 工具函数
print_info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

show_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║       🔐 Security Toolkit                 ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_help() {
    echo -e "${BOLD}用法:${NC} ./start.sh <命令> [--ssl]"
    echo ""
    echo -e "${BOLD}启动命令:${NC}"
    echo -e "  ${GREEN}dev${NC}         后台运行（开发模式，热重载）"
    echo -e "  ${GREEN}lite${NC}        后台运行（低内存模式，无热重载）"
    echo -e "  ${GREEN}run${NC}         前台运行 (推荐)"
    echo -e "  ${GREEN}prod${NC}        Docker 生产环境"
    echo ""
    echo -e "${BOLD}管理命令:${NC}"
    echo -e "  ${GREEN}stop${NC}        停止服务"
    echo -e "  ${GREEN}status${NC}      查看状态"
    echo -e "  ${GREEN}logs${NC}        查看日志"
    echo ""
    echo -e "${BOLD}工具命令:${NC}"
    echo -e "  ${GREEN}sync-api${NC}    同步 API 类型"
    echo -e "  ${GREEN}ssl${NC}         生成 SSL 证书"
    echo -e "  ${GREEN}clean${NC}       清理数据"
    echo ""
    echo -e "${BOLD}示例:${NC}"
    echo "  ./start.sh run"
    echo "  ./start.sh run --ssl"
}

# ==================== 检查函数 ====================
is_running() {
    case "$1" in
        backend)  
            # 优先检查端口，其次检查进程
            (curl -s --max-time 1 http://localhost:$BACKEND_PORT/api/docs > /dev/null 2>&1) || \
            (pgrep -f "uvicorn.*app.main" > /dev/null 2>&1)
            ;;
        frontend) 
            # 优先检查端口，其次检查进程
            (curl -s --max-time 1 http://localhost:$FRONTEND_PORT > /dev/null 2>&1) || \
            (pgrep -f "vite.*--port" > /dev/null 2>&1) || \
            (pgrep -f "nginx.*master" > /dev/null 2>&1)
            ;;
    esac
}

# 等待服务就绪
wait_for_service() {
    local service=$1
    local max_wait=${2:-10}
    local count=0
    
    while [ $count -lt $max_wait ]; do
        if is_running "$service"; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    return 1
}

# ==================== 初始化 ====================
init() {
    mkdir -p "$DATA_DIR" "$CERT_DIR"
    
    # 生成 .env
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        local secret=$(openssl rand -hex 32 2>/dev/null || echo "change-me-$(date +%s)")
        cat > "$PROJECT_DIR/.env" << EOF
# 数据库路径 - 留空则自动检测（推荐）
# DATABASE_URL=sqlite+aiosqlite:///./data/toolkit.db
JWT_SECRET_KEY=${secret}
DEBUG=false
CORS_ORIGINS=["http://localhost","http://localhost:80","https://localhost","https://localhost:443"]
EOF
        print_success "环境变量文件已生成"
    fi
}

setup_backend() {
    command -v python3 &> /dev/null || { print_error "Python3 未安装"; exit 1; }
    
    cd "$BACKEND_DIR"
    [ ! -d "venv" ] && { print_info "创建虚拟环境..."; python3 -m venv venv; }
    
    print_info "检查依赖..."
    ./venv/bin/pip install -q --upgrade pip
    ./venv/bin/pip install -q -r requirements.txt
}

setup_frontend() {
    command -v npm &> /dev/null || { print_error "npm 未安装"; exit 1; }
    
    cd "$FRONTEND_DIR"
    [ ! -d "node_modules" ] && { print_info "安装前端依赖..."; npm install; }
}

generate_ssl() {
    [ -f "$CERT_DIR/server.key" ] && [ -f "$CERT_DIR/server.crt" ] && return
    
    print_info "生成 SSL 证书..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt" \
        -subj "/CN=localhost" 2>/dev/null
    print_success "SSL 证书已生成"
}

# ==================== 服务管理 ====================
cmd_stop() {
    print_info "停止服务..."
    
    # PID 文件
    for f in "$DATA_DIR"/*.pid; do
        [ -f "$f" ] && { kill $(cat "$f") 2>/dev/null || true; rm -f "$f"; }
    done
    
    # 按进程名杀死所有相关进程
    pkill -f "uvicorn.*app.main" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "inotifywait.*src" 2>/dev/null || true
    
    # 停止 Nginx
    nginx -s stop 2>/dev/null || true
    
    # 杀死占用端口的进程
    fuser -k $BACKEND_PORT/tcp 2>/dev/null || true
    fuser -k $FRONTEND_PORT/tcp 2>/dev/null || true
    
    # 杀死所有 sec-toolkit 相关的 Python 和 Node 进程
    pkill -f "python.*sec-toolkit" 2>/dev/null || true
    pkill -f "node.*sec-toolkit" 2>/dev/null || true
    
    # Docker
    command -v docker &>/dev/null && (docker compose down 2>/dev/null || true)
    
    # 等待进程退出
    sleep 1
    
    print_success "服务已停止"
}

cmd_status() {
    echo ""
    echo -e "${BOLD}服务状态:${NC}"
    is_running "backend"  && echo -e "  ${GREEN}●${NC} 后端: 运行中" || echo -e "  ${RED}○${NC} 后端: 未运行"
    is_running "frontend" && echo -e "  ${GREEN}●${NC} 前端: 运行中" || echo -e "  ${RED}○${NC} 前端: 未运行"
    echo ""
}

cmd_dev() {
    local use_ssl=$1
    
    # 检查是否已运行
    if is_running "backend" || is_running "frontend"; then
        print_warning "服务已在运行"
        cmd_status
        return
    fi
    
    # 设置环境
    setup_backend
    setup_frontend
    [ "$use_ssl" = "true" ] && generate_ssl
    
    # SSL 参数
    local ssl_args=""
    [ "$use_ssl" = "true" ] && ssl_args="--ssl-keyfile=$CERT_DIR/server.key --ssl-certfile=$CERT_DIR/server.crt"
    
    # 启动后端
    print_info "启动后端..."
    cd "$BACKEND_DIR"
    nohup ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT $ssl_args > "$DATA_DIR/backend.log" 2>&1 &
    echo $! > "$DATA_DIR/backend.pid"
    wait_for_service "backend" 15 && print_success "后端已启动" || { print_error "后端启动失败，查看日志: cat $DATA_DIR/backend.log"; exit 1; }
    
    # 确保 Nginx 不占用端口（从 lite 模式切回时）
    nginx -s stop 2>/dev/null || true
    fuser -k $FRONTEND_PORT/tcp 2>/dev/null || true
    sleep 1
    
    # 启动前端
    print_info "启动前端..."
    cd "$FRONTEND_DIR"
    if [ "$use_ssl" = "true" ]; then
        VITE_HTTPS=true nohup npx vite --host --port $FRONTEND_PORT > "$DATA_DIR/frontend.log" 2>&1 &
    else
        nohup npx vite --host --port $FRONTEND_PORT > "$DATA_DIR/frontend.log" 2>&1 &
    fi
    echo $! > "$DATA_DIR/frontend.pid"
    wait_for_service "frontend" 10 && print_success "前端已启动" || { print_error "前端启动失败，查看日志: cat $DATA_DIR/frontend.log"; exit 1; }
    
    # 显示信息
    local proto="http"; [ "$use_ssl" = "true" ] && proto="https"
    echo ""
    print_success "启动完成！"
    echo -e "  ${GREEN}前端:${NC} ${proto}://localhost"
    echo -e "  ${GREEN}后端:${NC} ${proto}://localhost:${BACKEND_PORT}"
    echo -e "  ${GREEN}文档:${NC} ${proto}://localhost:${BACKEND_PORT}/api/docs"
}

cmd_lite() {
    local use_ssl=$1
    
    # 检查依赖
    command -v nginx &> /dev/null || { print_error "Nginx 未安装，lite 模式需要 Nginx"; exit 1; }
    command -v inotifywait &> /dev/null || { print_error "inotify-tools 未安装: apt install inotify-tools"; exit 1; }
    
    # 检查是否已运行
    if is_running "backend" || is_running "frontend"; then
        print_warning "服务已在运行"
        cmd_status
        return
    fi
    
    # 设置环境
    setup_backend
    setup_frontend
    
    # SSL 参数
    local ssl_args=""
    [ "$use_ssl" = "true" ] && { generate_ssl; ssl_args="--ssl-keyfile=$CERT_DIR/server.key --ssl-certfile=$CERT_DIR/server.crt"; }
    
    # 启动后端（热重载）
    print_info "启动后端..."
    cd "$BACKEND_DIR"
    nohup ./venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port $BACKEND_PORT --workers 1 $ssl_args > "$DATA_DIR/backend.log" 2>&1 &
    echo $! > "$DATA_DIR/backend.pid"
    wait_for_service "backend" 15 && print_success "后端已启动（热重载）" || { print_error "后端启动失败"; exit 1; }
    
    # 首次构建前端
    print_info "构建前端..."
    cd "$FRONTEND_DIR"
    npm run build > "$DATA_DIR/frontend-build.log" 2>&1
    if [ $? -ne 0 ]; then
        print_error "前端构建失败，查看日志: cat $DATA_DIR/frontend-build.log"
        exit 1
    fi
    print_success "前端构建完成"
    
    # 释放 80 端口
    fuser -k $FRONTEND_PORT/tcp 2>/dev/null || true
    sleep 1
    
    # 启动 Nginx
    print_info "启动 Nginx..."
    ln -sf /etc/nginx/sites-available/sec-toolkit /etc/nginx/sites-enabled/sec-toolkit
    rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/oob 2>/dev/null
    nginx -t > /dev/null 2>&1 || { print_error "Nginx 配置检查失败"; nginx -t; exit 1; }
    nginx > "$DATA_DIR/frontend.log" 2>&1
    wait_for_service "frontend" 5 && print_success "Nginx 已启动" || { print_error "Nginx 启动失败"; exit 1; }
    
    # 启动前端文件监听（自动重建，原子替换避免服务中断）
    print_info "启动前端文件监听..."
    nohup bash -c '
        cd "'"$FRONTEND_DIR"'"
        LOG="'"$DATA_DIR"'/frontend-watch.log"
        echo "[$(date)] 开始监听 src/ 目录..." > "$LOG"
        while true; do
            inotifywait -r -q -e modify,create,delete --exclude "node_modules|dist|\.git" src/ 2>/dev/null
            echo "[$(date)] 检测到文件变化，开始构建..." >> "$LOG"
            sleep 0.5
            VITE_OUT=dist_tmp npm run build -- --outDir dist_tmp >> "$LOG" 2>&1
            if [ $? -eq 0 ]; then
                rm -rf dist_old
                mv dist dist_old 2>/dev/null
                mv dist_tmp dist
                rm -rf dist_old
                echo "[$(date)] 构建成功 ✓" >> "$LOG"
            else
                rm -rf dist_tmp
                echo "[$(date)] 构建失败 ✗（保留旧版本）" >> "$LOG"
            fi
        done
    ' > /dev/null 2>&1 &
    echo $! > "$DATA_DIR/watcher.pid"
    print_success "文件监听已启动"
    
    # 显示信息
    local proto="http"; [ "$use_ssl" = "true" ] && proto="https"
    echo ""
    print_success "启动完成（低内存模式）！"
    echo -e "  ${GREEN}前端:${NC} ${proto}://localhost （Nginx）"
    echo -e "  ${GREEN}后端:${NC} ${proto}://localhost:${BACKEND_PORT}"
    echo -e "  ${GREEN}热重载:${NC}"
    echo -e "    后端: 自动重载"
    echo -e "    前端: 自动构建，刷新浏览器即可"
    echo -e "  ${GREEN}监听日志:${NC} cat $DATA_DIR/frontend-watch.log"
}

cmd_run() {
    local use_ssl=$1
    
    # 停止已有服务
    (is_running "backend" || is_running "frontend") && { print_warning "停止已有服务..."; cmd_stop; sleep 1; }
    
    # 设置环境
    setup_backend
    setup_frontend
    [ "$use_ssl" = "true" ] && generate_ssl
    
    # SSL 参数
    local ssl_args=""
    [ "$use_ssl" = "true" ] && ssl_args="--ssl-keyfile=$CERT_DIR/server.key --ssl-certfile=$CERT_DIR/server.crt"
    
    # 启动前端 (后台)
    print_info "启动前端..."
    cd "$FRONTEND_DIR"
    if [ "$use_ssl" = "true" ]; then
        VITE_HTTPS=true nohup npx vite --host --port $FRONTEND_PORT > "$DATA_DIR/frontend.log" 2>&1 &
    else
        nohup npx vite --host --port $FRONTEND_PORT > "$DATA_DIR/frontend.log" 2>&1 &
    fi
    echo $! > "$DATA_DIR/frontend.pid"
    
    local proto="http"; [ "$use_ssl" = "true" ] && proto="https"
    print_success "前端已启动: ${proto}://localhost"
    
    # 启动后端 (前台)
    print_info "启动后端 (前台)..."
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  后端日志 (Ctrl+C 停止)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}前端:${NC} ${proto}://localhost"
    echo -e "  ${GREEN}后端:${NC} ${proto}://localhost:${BACKEND_PORT}"
    echo -e "  ${GREEN}文档:${NC} ${proto}://localhost:${BACKEND_PORT}/api/docs"
    echo ""
    
    trap "echo ''; print_info '停止服务...'; cmd_stop; exit 0" SIGINT SIGTERM
    
    cd "$BACKEND_DIR"
    ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT $ssl_args
}

cmd_prod() {
    local use_ssl=$1
    command -v docker &>/dev/null || { print_error "Docker 未安装"; exit 1; }
    
    [ "$use_ssl" = "true" ] && generate_ssl
    
    print_info "启动 Docker..."
    cd "$PROJECT_DIR"
    
    if [ "$use_ssl" = "true" ]; then
        docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d --build
    else
        docker compose up -d --build
    fi
    
    local proto="http"; [ "$use_ssl" = "true" ] && proto="https"
    echo ""
    print_success "启动完成！"
    echo -e "  ${GREEN}前端:${NC} ${proto}://localhost"
    echo -e "  ${GREEN}后端:${NC} ${proto}://localhost:${BACKEND_PORT}"
}

cmd_logs() {
    echo "1) 后端  2) 前端  3) Docker"
    read -p "选择: " c
    case $c in
        1) tail -f "$DATA_DIR/backend.log" 2>/dev/null || print_warning "无日志" ;;
        2) tail -f "$DATA_DIR/frontend.log" 2>/dev/null || print_warning "无日志" ;;
        3) docker compose logs -f 2>/dev/null ;;
    esac
}

cmd_sync_api() {
    curl -s "http://localhost:${BACKEND_PORT}/api/openapi.json" > /dev/null 2>&1 || { print_error "后端未运行"; exit 1; }
    
    cd "$FRONTEND_DIR"
    [ ! -d "node_modules" ] && npm install
    
    print_info "生成 TypeScript 客户端..."
    npm run generate-api && print_success "完成！" || print_error "失败"
}

cmd_clean() {
    read -p "确定清理所有数据？[y/N] " c
    [ "$c" != "y" ] && [ "$c" != "Y" ] && return
    
    cmd_stop
    rm -rf "$DATA_DIR"/*.db "$DATA_DIR"/*.db-shm "$DATA_DIR"/*.db-wal "$DATA_DIR"/*.log "$DATA_DIR"/*.pid
    rm -rf "$FRONTEND_DIR/node_modules" "$FRONTEND_DIR/dist"
    rm -rf "$BACKEND_DIR/venv" "$BACKEND_DIR/__pycache__"
    docker compose down -v --rmi all 2>/dev/null || true
    print_success "清理完成"
}

# ==================== 主函数 ====================
main() {
    local cmd="" use_ssl="false"
    
    for arg in "$@"; do
        case "$arg" in
            --ssl) use_ssl="true" ;;
            *)     [ -z "$cmd" ] && cmd="$arg" ;;
        esac
    done
    
    case "$cmd" in
        ""|help|-h|--help)
            show_banner
            show_help
            ;;
        status)
            cmd_status
            ;;
        stop)
            cmd_stop
            ;;
        *)
            show_banner
            init
            case "$cmd" in
                dev)      cmd_dev "$use_ssl" ;;
                lite)     cmd_lite "$use_ssl" ;;
                run)      cmd_run "$use_ssl" ;;
                prod)     cmd_prod "$use_ssl" ;;
                logs)     cmd_logs ;;
                ssl)      generate_ssl ;;
                sync-api) cmd_sync_api ;;
                clean)    cmd_clean ;;
                *)        print_error "未知命令: $cmd"; show_help; exit 1 ;;
            esac
            ;;
    esac
}

main "$@"
