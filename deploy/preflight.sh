#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$REPO_ROOT"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
ENV_FILE="$PROJECT_DIR/.env"
DATA_DIR="${APP_DATA_DIR:-$PROJECT_DIR/data}"
BACKUP_DIR="${APP_BACKUP_DIR:-$PROJECT_DIR/backups}"
BACKEND_LOG_DIR="${APP_BACKEND_LOG_DIR:-$PROJECT_DIR/logs/backend}"
NGINX_LOG_DIR="${APP_NGINX_LOG_DIR:-$PROJECT_DIR/logs/nginx}"
UPLOAD_DIR="${APP_UPLOAD_DIR:-$DATA_DIR/uploads}"
API_PORT="${APP_API_PORT:-8000}"
HTTP_PORT="${APP_HTTP_PORT:-80}"
MIN_FREE_SPACE_MB="${APP_MIN_FREE_SPACE_MB:-3072}"
ALLOW_MISSING_ENV="false"
ALLOW_LEGACY_DEV="false"
ALLOW_BOUND_PORTS="false"
COMPOSE_CMD=()
FAILED="false"

is_current_project_pid() {
    local pid="$1"
    local cmd cwd

    [ -n "$pid" ] || return 1

    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [ -n "$cmd" ] && echo "$cmd" | grep -F "$PROJECT_DIR" >/dev/null 2>&1; then
        return 0
    fi

    if [ -d "/proc/$pid" ]; then
        cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
        if [ -n "$cwd" ] && echo "$cwd" | grep -F "$PROJECT_DIR" >/dev/null 2>&1; then
            return 0
        fi
    fi

    for pid_file in "$DATA_DIR"/*.pid; do
        [ -f "$pid_file" ] || continue
        if [ "$(cat "$pid_file" 2>/dev/null || true)" = "$pid" ]; then
            return 0
        fi
    done

    return 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --allow-missing-env)
            ALLOW_MISSING_ENV="true"
            shift
            ;;
        --allow-legacy-dev)
            ALLOW_LEGACY_DEV="true"
            shift
            ;;
        --allow-bound-ports)
            ALLOW_BOUND_PORTS="true"
            shift
            ;;
        *)
            print_error "未知参数: $1"
            exit 1
            ;;
    esac
done

detect_compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
    else
        print_error "未找到 Docker Compose"
        FAILED="true"
    fi
}

run_compose() {
    "${COMPOSE_CMD[@]}" "$@"
}

require_command() {
    if command -v "$1" >/dev/null 2>&1; then
        print_success "找到命令: $1"
    else
        print_error "缺少命令: $1"
        FAILED="true"
    fi
}

format_bytes() {
    python3 - "$1" <<'PY'
import sys

size = int(sys.argv[1])
units = ["B", "KB", "MB", "GB", "TB"]
value = float(size)
for unit in units:
    if value < 1024 or unit == units[-1]:
        if unit == "B":
            print(f"{int(value)}{unit}")
        else:
            print(f"{value:.1f}{unit}")
        break
    value /= 1024
PY
}

check_disk_space() {
    local free_bytes min_free_bytes

    case "$MIN_FREE_SPACE_MB" in
        ''|*[!0-9]*)
            print_error "APP_MIN_FREE_SPACE_MB 必须是非负整数，当前值: $MIN_FREE_SPACE_MB"
            FAILED="true"
            return
            ;;
    esac

    min_free_bytes=$((MIN_FREE_SPACE_MB * 1024 * 1024))
    free_bytes="$(df -Pk "$PROJECT_DIR" | awk 'NR==2 {print $4 * 1024}')"

    if [ "$free_bytes" -lt "$min_free_bytes" ]; then
        print_error "磁盘剩余空间不足: free=$(format_bytes "$free_bytes"), require>=$(format_bytes "$min_free_bytes")"
        print_error "建议先清理 backups/、Docker build cache、旧镜像或系统日志"
        FAILED="true"
        return
    fi

    print_success "磁盘剩余空间充足: free=$(format_bytes "$free_bytes")"
}

check_docker_daemon() {
    if docker info >/dev/null 2>&1; then
        print_success "Docker daemon 可用"
    else
        print_error "Docker daemon 不可用"
        FAILED="true"
    fi
}

check_compose_config() {
    [ "${#COMPOSE_CMD[@]}" -gt 0 ] || return

    if [ -f "$ENV_FILE" ]; then
        if run_compose -f "$COMPOSE_FILE" config >/dev/null 2>&1; then
            print_success "Compose 配置校验通过"
        else
            print_error "Compose 配置校验失败"
            FAILED="true"
        fi
        return
    fi

    if [ "$ALLOW_MISSING_ENV" = "true" ]; then
        print_warning ".env 不存在，跳过 Compose 配置校验"
    else
        print_error ".env 不存在"
        FAILED="true"
    fi
}

check_paths() {
    [ -f "$COMPOSE_FILE" ] && print_success "存在 compose 文件: $COMPOSE_FILE" || {
        print_error "缺少 compose 文件: $COMPOSE_FILE"
        FAILED="true"
    }

    [ -f "$ENV_FILE" ] && print_success "存在环境文件: $ENV_FILE" || {
        if [ "$ALLOW_MISSING_ENV" = "true" ]; then
            print_warning "环境文件不存在，安装脚本会自动生成: $ENV_FILE"
        else
            print_error "缺少环境文件: $ENV_FILE"
            FAILED="true"
        fi
    }

    mkdir -p "$DATA_DIR" "$BACKUP_DIR" "$BACKEND_LOG_DIR" "$NGINX_LOG_DIR"
    print_success "已确认目录可写: $DATA_DIR"
}

check_data_assets() {
    if [ -f "$DATA_DIR/toolkit.db" ]; then
        print_success "存在数据库: $DATA_DIR/toolkit.db"
    else
        print_warning "未找到数据库: $DATA_DIR/toolkit.db"
    fi

    if [ -d "$UPLOAD_DIR" ] && find "$UPLOAD_DIR" -mindepth 1 -print -quit >/dev/null 2>&1; then
        print_success "存在上传文件目录且非空: $UPLOAD_DIR"
    else
        print_info "上传文件目录为空或不存在: $UPLOAD_DIR"
    fi
}

check_legacy_dev_processes() {
    local legacy_found="false"

    if pgrep -f "$PROJECT_DIR/backend/venv/bin/uvicorn app.main:app" >/dev/null 2>&1; then
        print_warning "检测到旧的 start.sh dev 后端进程"
        legacy_found="true"
    fi

    if pgrep -f "node.*$PROJECT_DIR/frontend.*vite" >/dev/null 2>&1; then
        print_warning "检测到旧的 start.sh dev 前端进程"
        legacy_found="true"
    fi

    if [ "$legacy_found" = "true" ] && [ "$ALLOW_LEGACY_DEV" != "true" ]; then
        FAILED="true"
    fi
}

check_port_owner() {
    local port="$1"

    command -v lsof >/dev/null 2>&1 || return

    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        print_success "端口空闲: $port"
        return
    fi

    local pids cmd pid
    pids="$(lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
    cmd="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN | tail -n +2)"
    if [ "$ALLOW_BOUND_PORTS" = "true" ]; then
        print_warning "端口已占用但已允许继续: $port"
        echo "$cmd"
        return
    fi

    for pid in $pids; do
        if ! is_current_project_pid "$pid"; then
            print_error "端口被非当前项目进程占用: $port"
            echo "$cmd"
            FAILED="true"
            return
        fi
    done

    print_warning "端口被当前项目进程占用: $port"
}

main() {
    require_command docker
    require_command git
    require_command curl
    require_command python3
    detect_compose_cmd
    check_docker_daemon
    check_paths
    check_compose_config
    check_data_assets
    check_disk_space
    check_legacy_dev_processes
    check_port_owner "$API_PORT"
    check_port_owner "$HTTP_PORT"

    if [ "$FAILED" = "true" ]; then
        print_error "预检失败"
        exit 1
    fi

    print_success "预检通过"
}

main "$@"
