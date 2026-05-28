#!/usr/bin/env python3
"""
按邮箱重置用户密码脚本。

使用方式:
  python backend/scripts/reset_user_password.py --email hsin.cao@zoom.us --password 'newpass'
  python backend/scripts/reset_user_password.py --email hsin.cao@zoom.us --password 'newpass' --verify
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db_path() -> Path:
    """返回默认 SQLite 数据库路径。"""
    # 当前文件: backend/scripts/reset_user_password.py
    # 项目根目录: ../../
    return Path(__file__).resolve().parents[2] / "data" / "toolkit.db"


def reset_password(email: str, password: str, verify: bool) -> None:
    """重置指定邮箱用户密码。"""
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"用户不存在: {email}")

        user_id, user_email = row
        password_hash = pwd_context.hash(password)
        cur.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ?",
            (password_hash, datetime.now(UTC).replace(tzinfo=None).isoformat(), email),
        )
        conn.commit()

        print(f"密码已更新: {user_email} (id={user_id})")

        if verify:
            cur.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
            stored_hash = cur.fetchone()[0]
            ok = pwd_context.verify(password, stored_hash)
            print(f"哈希校验: {'通过' if ok else '失败'}")
    finally:
        conn.close()


def main() -> None:
    """脚本入口。"""
    parser = argparse.ArgumentParser(description="按邮箱重置用户密码")
    parser.add_argument("--email", required=True, help="用户邮箱")
    parser.add_argument("--password", required=True, help="新密码")
    parser.add_argument("--verify", action="store_true", help="更新后执行哈希校验")
    args = parser.parse_args()

    reset_password(email=args.email, password=args.password, verify=args.verify)


if __name__ == "__main__":
    main()
