#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -d "$REPO_ROOT/backend" ] && [ -f "$REPO_ROOT/docker-compose.yml" ]; then
    MODE="repo"
    APP_HOME="$REPO_ROOT"
    COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"
    ENV_EXAMPLE="$REPO_ROOT/env.example"
    BACKUP_SCRIPT="$SCRIPT_DIR/backup-db.sh"
else
    MODE="offline"
    APP_HOME="$SCRIPT_DIR"
    COMPOSE_FILE="$SCRIPT_DIR/docker-compose.prod.yml"
    ENV_EXAMPLE=""
    BACKUP_SCRIPT="$SCRIPT_DIR/backup-db.sh"
fi

ENV_FILE="$APP_HOME/.env"
DATA_DIR="${APP_DATA_DIR:-$APP_HOME/data}"
BACKUP_DIR="${APP_BACKUP_DIR:-$APP_HOME/backups}"
API_PORT="${APP_API_PORT:-8000}"
HTTP_PORT="${APP_HTTP_PORT:-80}"
COMPOSE_CMD=()

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

create_env_file() {
    if [ -f "$ENV_FILE" ]; then
        print_info "配置文件已存在，跳过生成: $ENV_FILE"
        return
    fi

    local jwt_secret
    jwt_secret="$(openssl rand -hex 32 2>/dev/null || date +%s | shasum | awk '{print $1}')"

    if [ -n "$ENV_EXAMPLE" ] && [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        cat > "$ENV_FILE" <<'EOF'
JWT_SECRET_KEY=change-this-to-a-long-random-secret
DEBUG=false
CORS_ORIGINS=["http://localhost","https://localhost"]
CALLBACK_BASE_URL=
SSL_ENABLED=false
SSL_KEYFILE=
SSL_CERTFILE=
DEFAULT_LLM_PROVIDER=
DEFAULT_LLM_API_KEY=
DEFAULT_LLM_BASE_URL=
DEFAULT_LLM_MODEL=
INTENT_LLM_MODEL=
SUMMARY_LLM_MODEL=
DUAL_LLM_ENABLED=true
EOF
    fi

    python3 - "$ENV_FILE" "$jwt_secret" <<'PY'
import pathlib
import re
import sys

env_path = pathlib.Path(sys.argv[1])
secret = sys.argv[2]
content = env_path.read_text(encoding="utf-8")

if re.search(r"^JWT_SECRET_KEY=.*$", content, re.M):
    content = re.sub(r"^JWT_SECRET_KEY=.*$", f"JWT_SECRET_KEY={secret}", content, count=1, flags=re.M)
else:
    content += f"\nJWT_SECRET_KEY={secret}\n"

env_path.write_text(content, encoding="utf-8")
PY

    print_success "已生成配置文件: $ENV_FILE"
}

stop_legacy_processes() {
    if [ "$MODE" != "repo" ]; then
        return
    fi

    local stopped="false"
    local pid_file pid cmd

    for pid_file in "$DATA_DIR"/*.pid; do
        [ -f "$pid_file" ] || continue
        pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [ -n "${pid:-}" ] && ps -p "$pid" >/dev/null 2>&1; then
            cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
            if echo "$cmd" | grep -F "$APP_HOME" >/dev/null 2>&1; then
                print_info "停止旧进程 PID=$pid"
                kill "$pid" 2>/dev/null || true
                stopped="true"
            fi
        fi
        rm -f "$pid_file"
    done

    pkill -f "$APP_HOME/backend/venv/bin/uvicorn app.main:app" 2>/dev/null && stopped="true" || true
    pkill -f "$APP_HOME/frontend/.*/vite" 2>/dev/null && stopped="true" || true
    pkill -f "node.*$APP_HOME/frontend.*vite" 2>/dev/null && stopped="true" || true

    if [ "$stopped" = "true" ]; then
        sleep 2
    fi
}

assert_ports_available() {
    local ports=("${APP_API_PORT:-8000}" "${APP_HTTP_PORT:-80}")
    local port

    command -v lsof >/dev/null 2>&1 || return 0

    for port in "${ports[@]}"; do
        if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            print_error "端口 $port 已被其他进程占用，请先释放"
            lsof -nP -iTCP:"$port" -sTCP:LISTEN
            exit 1
        fi
    done
}

assert_no_unexpected_port_owners() {
    local ports=("${APP_API_PORT:-8000}" "${APP_HTTP_PORT:-80}")
    local port pid cmd

    command -v lsof >/dev/null 2>&1 || return 0

    for port in "${ports[@]}"; do
        while read -r pid; do
            [ -n "$pid" ] || continue
            cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
            if [ -z "$cmd" ]; then
                continue
            fi
            if echo "$cmd" | grep -F "$APP_HOME" >/dev/null 2>&1; then
                continue
            fi
            print_error "端口 $port 被非当前项目进程占用，停止切换"
            echo "$cmd"
            exit 1
        done < <(lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u)
    done
}

wait_for_backend() {
    local attempts=30
    local health_url="http://127.0.0.1:${API_PORT}/health"

    for _ in $(seq 1 "$attempts"); do
        if curl -fsS --max-time 3 "$health_url" >/dev/null 2>&1; then
            print_success "后端健康检查通过: $health_url"
            return 0
        fi
        sleep 2
    done

    print_error "后端健康检查失败: $health_url"
    return 1
}

deploy_from_repo() {
    print_info "使用源码仓库模式部署"

    mkdir -p "$DATA_DIR" "$BACKUP_DIR"
    create_env_file

    if [ -x "$BACKUP_SCRIPT" ]; then
        "$BACKUP_SCRIPT"
    fi

    cd "$APP_HOME"
    run_compose -f "$COMPOSE_FILE" config >/dev/null
    run_compose -f "$COMPOSE_FILE" build
    assert_no_unexpected_port_owners
    stop_legacy_processes
    assert_ports_available
    run_compose -f "$COMPOSE_FILE" run --rm --no-deps backend python scripts/migrate_db.py
    run_compose -f "$COMPOSE_FILE" up -d
}

deploy_from_offline_package() {
    print_info "使用离线镜像包模式部署"

    [ -f "$SCRIPT_DIR/sec-toolkit-images.tar" ] || {
        print_error "未找到离线镜像文件: $SCRIPT_DIR/sec-toolkit-images.tar"
        exit 1
    }

    mkdir -p "$DATA_DIR" "$BACKUP_DIR"
    create_env_file

    if [ -x "$BACKUP_SCRIPT" ]; then
        "$BACKUP_SCRIPT"
    fi

    cd "$APP_HOME"
    print_info "加载 Docker 镜像..."
    docker load -i "$SCRIPT_DIR/sec-toolkit-images.tar"
    run_compose -f "$COMPOSE_FILE" config >/dev/null
    run_compose -f "$COMPOSE_FILE" run --rm --no-deps backend python scripts/migrate_db.py
    run_compose -f "$COMPOSE_FILE" up -d
}

main() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Security Toolkit 安装/初始化         ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
    echo ""

    require_command docker
    require_command curl
    require_command python3
    detect_compose_cmd

    if [ "$MODE" = "repo" ]; then
        deploy_from_repo
    else
        deploy_from_offline_package
    fi

    wait_for_backend

    echo ""
    print_success "部署完成"
    echo "  前端:    http://127.0.0.1:${HTTP_PORT}"
    echo "  API 文档: http://127.0.0.1:${API_PORT}/api/docs"
    echo "  数据目录: $DATA_DIR"
    echo "  备份目录: $BACKUP_DIR"
}

main "$@"
