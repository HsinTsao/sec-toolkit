#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
BACKUP_SCRIPT="$SCRIPT_DIR/backup-db.sh"
PREFLIGHT_SCRIPT="$SCRIPT_DIR/preflight.sh"
COMPOSE_CMD=()
BACKEND_LOG_DIR="${APP_BACKEND_LOG_DIR:-$PROJECT_DIR/logs/backend}"
NGINX_LOG_DIR="${APP_NGINX_LOG_DIR:-$PROJECT_DIR/logs/nginx}"

SKIP_GIT="false"
BRANCH=""

while [ $# -gt 0 ]; do
    case "$1" in
        --skip-git)
            SKIP_GIT="true"
            shift
            ;;
        --branch)
            BRANCH="${2:-}"
            shift 2
            ;;
        *)
            print_error "未知参数: $1"
            exit 1
            ;;
    esac
done

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        print_error "$1 未安装"
        exit 1
    }
}

detect_compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=(docker-compose)
    else
        print_error "未找到 Docker Compose，请安装 docker compose 插件或 docker-compose"
        exit 1
    fi
}

run_compose() {
    "${COMPOSE_CMD[@]}" "$@"
}

run_preflight() {
    [ -x "$PREFLIGHT_SCRIPT" ] || return 0
    "$PREFLIGHT_SCRIPT" --allow-bound-ports
}

ensure_no_legacy_dev_processes() {
    if pgrep -f "$PROJECT_DIR/backend/venv/bin/uvicorn app.main:app" >/dev/null 2>&1; then
        print_error "检测到旧的 start.sh dev 后端进程，请先停掉再发布"
        exit 1
    fi

    if pgrep -f "node.*$PROJECT_DIR/frontend.*vite" >/dev/null 2>&1; then
        print_error "检测到旧的 start.sh dev 前端进程，请先停掉再发布"
        exit 1
    fi
}

wait_for_backend() {
    local api_port="${APP_API_PORT:-8000}"
    local health_url="http://127.0.0.1:${api_port}/health"

    for _ in $(seq 1 30); do
        if curl -fsS --max-time 3 "$health_url" >/dev/null 2>&1; then
            print_success "后端健康检查通过: $health_url"
            return 0
        fi
        sleep 2
    done

    print_error "后端健康检查失败: $health_url"
    return 1
}

update_code() {
    local tracked_changes
    tracked_changes="$(git -C "$PROJECT_DIR" status --short --untracked-files=no)"
    if [ -n "$tracked_changes" ]; then
        print_error "仓库存在未提交的 tracked 改动，停止自动 git pull"
        echo "$tracked_changes"
        exit 1
    fi

    local target_branch="$BRANCH"
    if [ -z "$target_branch" ]; then
        target_branch="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)"
    fi

    print_info "更新代码分支: $target_branch"
    git -C "$PROJECT_DIR" fetch origin
    git -C "$PROJECT_DIR" checkout "$target_branch"
    git -C "$PROJECT_DIR" pull --ff-only origin "$target_branch"
}

main() {
    require_command docker
    require_command git
    require_command curl
    require_command python3
    detect_compose_cmd
    run_preflight

    [ -f "$COMPOSE_FILE" ] || {
        print_error "未找到 compose 文件: $COMPOSE_FILE"
        exit 1
    }

    if [ "$SKIP_GIT" != "true" ]; then
        update_code
    else
        print_info "跳过 git 更新"
    fi

    ensure_no_legacy_dev_processes

    if [ -x "$BACKUP_SCRIPT" ]; then
        "$BACKUP_SCRIPT"
    fi

    mkdir -p "$BACKEND_LOG_DIR" "$NGINX_LOG_DIR"

    cd "$PROJECT_DIR"
    run_compose -f "$COMPOSE_FILE" config >/dev/null
    run_compose -f "$COMPOSE_FILE" build
    run_compose -f "$COMPOSE_FILE" run --rm --no-deps backend python scripts/migrate_db.py
    run_compose -f "$COMPOSE_FILE" up -d

    wait_for_backend
    run_compose -f "$COMPOSE_FILE" ps
}

main "$@"
