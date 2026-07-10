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
POC_FILE_DIR="${APP_POC_FILE_DIR:-$DATA_DIR/poc-files}"
BACKUP_KEEP_COUNT="${APP_BACKUP_KEEP_COUNT:-3}"

mkdir -p "$DATA_DIR" "$BACKUP_DIR" "$BACKEND_LOG_DIR" "$NGINX_LOG_DIR"

TIMESTAMP="$(date +%F-%H%M%S)"
SNAPSHOT_DIR="$BACKUP_DIR/snapshot-${TIMESTAMP}"

bytes_for_file() {
    local path="$1"
    [ -f "$path" ] || {
        echo 0
        return
    }

    if stat -c %s "$path" >/dev/null 2>&1; then
        stat -c %s "$path"
    else
        stat -f %z "$path"
    fi
}

bytes_for_dir() {
    local path="$1"
    [ -d "$path" ] || {
        echo 0
        return
    }

    du -sk "$path" 2>/dev/null | awk '{print $1 * 1024}'
}

bytes_available_for_path() {
    local path="$1"
    df -Pk "$path" | awk 'NR==2 {print $4 * 1024}'
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

prune_old_snapshots() {
    local keep_count="$BACKUP_KEEP_COUNT"
    local keep_existing
    local snapshots=()
    local old_snapshot

    case "$keep_count" in
        ''|*[!0-9]*)
            echo "[ERROR] APP_BACKUP_KEEP_COUNT 必须是非负整数，当前值: $keep_count" >&2
            exit 1
            ;;
    esac

    if [ "$keep_count" -eq 0 ]; then
        echo "[INFO] 已禁用自动清理旧快照: APP_BACKUP_KEEP_COUNT=0"
        return
    fi

    keep_existing=$((keep_count - 1))
    while IFS= read -r old_snapshot; do
        [ -n "$old_snapshot" ] || continue
        snapshots+=("$old_snapshot")
    done < <(find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d -name 'snapshot-*' -print 2>/dev/null | sort -r)

    if [ "${#snapshots[@]}" -le "$keep_existing" ]; then
        return
    fi

    for old_snapshot in "${snapshots[@]:$keep_existing}"; do
        rm -rf "$old_snapshot"
        echo "[INFO] 已删除旧快照: $old_snapshot"
    done
}

estimate_required_bytes() {
    local total=0
    local db_wal="${DB_FILE}-wal"
    local db_shm="${DB_FILE}-shm"
    local legacy_logs_size=0

    total=$((total + $(bytes_for_file "$DB_FILE")))
    total=$((total + $(bytes_for_file "$db_wal")))
    total=$((total + $(bytes_for_file "$db_shm")))
    total=$((total + $(bytes_for_dir "$UPLOAD_DIR")))
    total=$((total + $(bytes_for_dir "$POC_FILE_DIR")))
    total=$((total + $(bytes_for_dir "$BACKEND_LOG_DIR")))
    total=$((total + $(bytes_for_dir "$NGINX_LOG_DIR")))

    [ -f "$DATA_DIR/backend.log" ] && legacy_logs_size=$((legacy_logs_size + $(bytes_for_file "$DATA_DIR/backend.log")))
    [ -f "$DATA_DIR/backend.error.log" ] && legacy_logs_size=$((legacy_logs_size + $(bytes_for_file "$DATA_DIR/backend.error.log")))
    [ -f "$DATA_DIR/frontend.log" ] && legacy_logs_size=$((legacy_logs_size + $(bytes_for_file "$DATA_DIR/frontend.log")))
    [ -f "$DATA_DIR/backend.stdout.log" ] && legacy_logs_size=$((legacy_logs_size + $(bytes_for_file "$DATA_DIR/backend.stdout.log")))
    total=$((total + legacy_logs_size))

    # 留一部分冗余给 sqlite backup / tar / docker compose 后续步骤。
    total=$((total + 64 * 1024 * 1024))
    echo "$total"
}

check_free_space() {
    local required available
    required="$(estimate_required_bytes)"
    available="$(bytes_available_for_path "$BACKUP_DIR")"

    if [ "$available" -lt "$required" ]; then
        echo "[ERROR] 磁盘剩余空间不足，停止创建发布快照" >&2
        echo "[ERROR] 备份目录: $BACKUP_DIR" >&2
        echo "[ERROR] 预估所需: $(format_bytes "$required")" >&2
        echo "[ERROR] 当前可用: $(format_bytes "$available")" >&2
        echo "[ERROR] 请先清理旧快照、Docker 镜像/构建缓存或扩容磁盘" >&2
        exit 1
    fi

    echo "[INFO] 备份空间检查通过: need=$(format_bytes "$required"), free=$(format_bytes "$available")"
}

write_manifest() {
    cat > "$SNAPSHOT_DIR/manifest.txt" <<EOF
timestamp=${TIMESTAMP}
app_home=${APP_HOME}
data_dir=${DATA_DIR}
db_file=${DB_FILE}
upload_dir=${UPLOAD_DIR}
poc_file_dir=${POC_FILE_DIR}
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
from pathlib import Path

source_path, backup_path = sys.argv[1], sys.argv[2]
source_conn = None
backup_conn = None

try:
    source_conn = sqlite3.connect(source_path)
    backup_conn = sqlite3.connect(backup_path)
    source_conn.backup(backup_conn)
except sqlite3.OperationalError as exc:
    msg = str(exc).lower()
    if "database or disk is full" in msg:
        print(f"[ERROR] SQLite 备份失败: 目标磁盘空间不足 ({backup_path})", file=sys.stderr)
    else:
        print(f"[ERROR] SQLite 备份失败: {exc}", file=sys.stderr)
    Path(backup_path).unlink(missing_ok=True)
    sys.exit(1)
finally:
    if backup_conn is not None:
        backup_conn.close()
    if source_conn is not None:
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

prune_old_snapshots
check_free_space
mkdir -p "$SNAPSHOT_DIR"
write_manifest
backup_database
archive_dir_if_exists "$UPLOAD_DIR" "uploads.tar.gz"
archive_dir_if_exists "$POC_FILE_DIR" "poc-files.tar.gz"
archive_dir_if_exists "$BACKEND_LOG_DIR" "backend-logs.tar.gz"
archive_dir_if_exists "$NGINX_LOG_DIR" "nginx-logs.tar.gz"
archive_legacy_logs_if_exists

echo "[INFO] 备份快照完成: $SNAPSHOT_DIR"
