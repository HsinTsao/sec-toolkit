#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -d "$REPO_ROOT/backend" ] && [ -f "$REPO_ROOT/docker-compose.yml" ]; then
    APP_HOME="$REPO_ROOT"
else
    APP_HOME="$SCRIPT_DIR"
fi

DATA_DIR="${APP_DATA_DIR:-$APP_HOME/data}"
BACKUP_DIR="${APP_BACKUP_DIR:-$APP_HOME/backups}"
BACKEND_LOG_DIR="${APP_BACKEND_LOG_DIR:-$APP_HOME/logs/backend}"
NGINX_LOG_DIR="${APP_NGINX_LOG_DIR:-$APP_HOME/logs/nginx}"
DB_FILE="${SQLITE_DB_FILE:-$DATA_DIR/toolkit.db}"
UPLOAD_DIR="${APP_UPLOAD_DIR:-$DATA_DIR/uploads}"

mkdir -p "$DATA_DIR" "$BACKUP_DIR" "$BACKEND_LOG_DIR" "$NGINX_LOG_DIR"

TIMESTAMP="$(date +%F-%H%M%S)"
SNAPSHOT_DIR="$BACKUP_DIR/snapshot-${TIMESTAMP}"
mkdir -p "$SNAPSHOT_DIR"

write_manifest() {
    cat > "$SNAPSHOT_DIR/manifest.txt" <<EOF
timestamp=${TIMESTAMP}
app_home=${APP_HOME}
data_dir=${DATA_DIR}
db_file=${DB_FILE}
upload_dir=${UPLOAD_DIR}
backend_log_dir=${BACKEND_LOG_DIR}
nginx_log_dir=${NGINX_LOG_DIR}
EOF
}

backup_database() {
    if [ ! -f "$DB_FILE" ]; then
        echo "[INFO] 未找到数据库文件，跳过数据库备份: $DB_FILE"
        return
    fi

    python3 - "$DB_FILE" "$SNAPSHOT_DIR/toolkit.db" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1], sys.argv[2]
source_conn = sqlite3.connect(source_path)
backup_conn = sqlite3.connect(backup_path)
source_conn.backup(backup_conn)
backup_conn.close()
source_conn.close()
PY
    echo "[INFO] 数据库已备份到: $SNAPSHOT_DIR/toolkit.db"
}

archive_dir_if_exists() {
    local source_dir="$1"
    local archive_name="$2"

    if [ ! -d "$source_dir" ]; then
        return
    fi

    if ! find "$source_dir" -mindepth 1 -print -quit >/dev/null 2>&1; then
        return
    fi

    tar -czf "$SNAPSHOT_DIR/$archive_name" -C "$(dirname "$source_dir")" "$(basename "$source_dir")"
    echo "[INFO] 已归档: $SNAPSHOT_DIR/$archive_name"
}

archive_legacy_logs_if_exists() {
    local legacy_logs=()
    [ -f "$DATA_DIR/backend.log" ] && legacy_logs+=("backend.log")
    [ -f "$DATA_DIR/backend.error.log" ] && legacy_logs+=("backend.error.log")
    [ -f "$DATA_DIR/frontend.log" ] && legacy_logs+=("frontend.log")
    [ -f "$DATA_DIR/backend.stdout.log" ] && legacy_logs+=("backend.stdout.log")

    [ "${#legacy_logs[@]}" -gt 0 ] || return

    tar -czf "$SNAPSHOT_DIR/legacy-data-logs.tar.gz" -C "$DATA_DIR" "${legacy_logs[@]}"
    echo "[INFO] 已归档旧日志: $SNAPSHOT_DIR/legacy-data-logs.tar.gz"
}

write_manifest
backup_database
archive_dir_if_exists "$UPLOAD_DIR" "uploads.tar.gz"
archive_dir_if_exists "$BACKEND_LOG_DIR" "backend-logs.tar.gz"
archive_dir_if_exists "$NGINX_LOG_DIR" "nginx-logs.tar.gz"
archive_legacy_logs_if_exists

echo "[INFO] 备份快照完成: $SNAPSHOT_DIR"
