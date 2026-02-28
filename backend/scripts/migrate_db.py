#!/usr/bin/env python3
"""
数据库迁移脚本

用于创建新表和更新现有表结构。
使用方式: python scripts/migrate_db.py

注意: 此脚本会自动创建缺失的表，但不会修改已存在的表结构。
如需修改已有表，请手动编写 ALTER TABLE 语句。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.database import engine, Base, init_db
from app.models import *  # 导入所有模型


async def get_existing_tables():
    """获取现有表列表"""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        return [row[0] for row in result.fetchall()]


async def migrate():
    """执行数据库迁移"""
    print("=" * 50)
    print("数据库迁移脚本")
    print("=" * 50)
    
    # 获取现有表
    existing_tables = await get_existing_tables()
    print(f"\n现有表: {len(existing_tables)} 个")
    for table in sorted(existing_tables):
        print(f"  - {table}")
    
    # 获取模型定义的表
    model_tables = set(Base.metadata.tables.keys())
    print(f"\n模型定义的表: {len(model_tables)} 个")
    for table in sorted(model_tables):
        print(f"  - {table}")
    
    # 找出需要创建的新表
    new_tables = model_tables - set(existing_tables)
    if new_tables:
        print(f"\n需要创建的新表: {len(new_tables)} 个")
        for table in sorted(new_tables):
            print(f"  - {table}")
    else:
        print("\n没有需要创建的新表")
    
    # 执行迁移
    print("\n开始迁移...")
    try:
        await init_db()
        print("✓ 迁移完成!")
        
        # 验证
        new_existing = await get_existing_tables()
        created = set(new_existing) - set(existing_tables)
        if created:
            print(f"\n已创建的表:")
            for table in sorted(created):
                print(f"  ✓ {table}")
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        raise


async def show_table_schema(table_name: str):
    """显示表结构"""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"PRAGMA table_info({table_name})")
        )
        columns = result.fetchall()
        
        print(f"\n表 {table_name} 结构:")
        print("-" * 60)
        print(f"{'列名':<20} {'类型':<15} {'可空':<6} {'主键':<6}")
        print("-" * 60)
        for col in columns:
            # col: (cid, name, type, notnull, dflt_value, pk)
            nullable = "是" if col[3] == 0 else "否"
            pk = "是" if col[5] == 1 else ""
            print(f"{col[1]:<20} {col[2]:<15} {nullable:<6} {pk:<6}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库迁移脚本")
    parser.add_argument("--show", type=str, help="显示指定表的结构")
    parser.add_argument("--list", action="store_true", help="只列出表，不执行迁移")
    args = parser.parse_args()
    
    if args.show:
        await show_table_schema(args.show)
    elif args.list:
        tables = await get_existing_tables()
        print("现有表:")
        for table in sorted(tables):
            print(f"  - {table}")
    else:
        await migrate()


if __name__ == "__main__":
    asyncio.run(main())
