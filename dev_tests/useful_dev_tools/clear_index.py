"""
清除 AI 索引目录

Usage:
    python dev_tests/useful_dev_tools/clear_index.py
"""
import shutil
from pathlib import Path


def clear_index(index_dir: str = ".memo_indexes"):
    """清除索引目录"""
    index_path = Path(index_dir)

    if index_path.exists():
        shutil.rmtree(index_path)
        print(f"Index directory '{index_dir}' cleared successfully.")
    else:
        print(f"Index directory '{index_dir}' does not exist.")


if __name__ == "__main__":
    import sys

    # 默认索引目录
    index_dir = ".memo_indexes"

    # 支持命令行参数指定索引目录
    if len(sys.argv) > 1:
        index_dir = sys.argv[1]

    clear_index(index_dir)
    print("\nNote: Restart AI service to load empty index.")
