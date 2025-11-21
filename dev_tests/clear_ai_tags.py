#!/usr/bin/env python3
"""
清除所有 memo 的 AI 标签 (开发测试工具)

使用方法:
    python dev_tests/clear_ai_tags.py
    python dev_tests/clear_ai_tags.py --db memos_dev.db
"""
import sqlite3
import json
import argparse
from pathlib import Path


def clear_ai_tags(db_path: str):
    """清除数据库中所有 memo 的 AI 标签"""
    db_file = Path(db_path)

    if not db_file.exists():
        print(f"❌ 错误: 数据库文件不存在: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 统计清除前的数据
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN json_extract(payload, '$.aiTags') IS NOT NULL THEN 1 ELSE 0 END) as with_ai_tags
            FROM memo
        """)
        total, with_ai_tags = cursor.fetchone()

        print(f"\n📊 清除前统计:")
        print(f"   总备忘录数: {total}")
        print(f"   包含 AI 标签: {with_ai_tags or 0}")

        if not with_ai_tags:
            print("\n✓ 没有需要清除的 AI 标签")
            conn.close()
            return True

        # 清除 AI 标签
        print(f"\n🔄 正在清除 {with_ai_tags} 条备忘录的 AI 标签...")
        cursor.execute("""
            UPDATE memo
            SET payload = json_remove(payload, '$.aiTags')
            WHERE json_extract(payload, '$.aiTags') IS NOT NULL
        """)

        affected_rows = cursor.rowcount
        conn.commit()

        # 统计清除后的数据
        cursor.execute("""
            SELECT
                SUM(CASE WHEN json_extract(payload, '$.aiTags') IS NOT NULL THEN 1 ELSE 0 END)
            FROM memo
        """)
        remaining = cursor.fetchone()[0] or 0

        print(f"\n✅ 清除完成:")
        print(f"   已清除: {affected_rows} 条")
        print(f"   剩余 AI 标签: {remaining}")

        conn.close()
        return True

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="清除开发数据库中的所有 AI 标签"
    )
    parser.add_argument(
        "--db",
        default="memos_dev.db",
        help="数据库文件路径 (默认: memos_dev.db)"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("清除 AI 标签工具 (开发测试用)")
    print("=" * 50)

    success = clear_ai_tags(args.db)

    if not success:
        exit(1)


if __name__ == "__main__":
    main()
