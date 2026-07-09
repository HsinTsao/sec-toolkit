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
DB_FILE="${SQLITE_DB_FILE:-$DATA_DIR/toolkit.db}"

mkdir -p "$DATA_DIR" "$BACKUP_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "[INFO] 未找到数据库文件，跳过备份: $DB_FILE"
    exit 0
fi

TIMESTAMP="$(date +%F-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/toolkit-${TIMESTAMP}.db"

python3 - "$DB_FILE" "$BACKUP_FILE" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1], sys.argv[2]
source_conn = sqlite3.connect(source_path)
backup_conn = sqlite3.connect(backup_path)
source_conn.backup(backup_conn)
backup_conn.close()
source_conn.close()
PY

echo "[INFO] 数据库已备份到: $BACKUP_FILE"
